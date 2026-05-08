import streamlit as st
import pandas as pd
import requests
import time
import datetime
import re

st.set_page_config(
    page_title="입금 바랍니다 — 대시보드",
    page_icon="▶",
    layout="wide",
)

st.markdown("""
<style>
html, body, [data-testid="stApp"] {
    background-color: #0d0d0d;
    color: #e0e0e0;
}
[data-testid="stSidebar"] { background-color: #141414; border-right: 1px solid #222; }
[data-testid="stSidebar"] label { color: #f0f0f0; }
.stButton > button {
    background-color: #ff0000;
    color: #fff;
    border: none;
    border-radius: 6px;
    font-weight: 600;
    padding: 0.4rem 1.2rem;
}
.stButton > button:hover { background-color: #cc0000; color: #fff; }
h1 { color: #ffffff; font-weight: 800; }
h2, h3 { color: #f0f0f0; font-weight: 700; }
.live-badge {
    display: inline-block;
    background: #ff0000;
    color: #fff;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 4px;
    margin-left: 8px;
    vertical-align: middle;
    letter-spacing: 1px;
}

/* 가로 스크롤 카드 래퍼 */
.scroll-wrapper {
    overflow-x: auto;
    padding-bottom: 12px;
    scrollbar-width: thin;
    scrollbar-color: #ff0000 #1a1a1a;
}
.scroll-wrapper::-webkit-scrollbar { height: 6px; }
.scroll-wrapper::-webkit-scrollbar-track { background: #1a1a1a; }
.scroll-wrapper::-webkit-scrollbar-thumb { background: #ff0000; border-radius: 3px; }

.card-row {
    display: flex;
    gap: 16px;
    width: max-content;
    padding: 8px 4px;
}

.ep-card {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 12px;
    width: 220px;
    overflow: hidden;
    cursor: pointer;
    transition: border-color 0.2s, transform 0.2s;
    flex-shrink: 0;
}
.ep-card:hover { border-color: #ff0000; transform: translateY(-2px); }
.ep-card.active { border-color: #ff0000; }

.ep-card img {
    width: 100%;
    height: 124px;
    object-fit: cover;
    display: block;
}
.ep-card-body { padding: 10px 12px; }
.ep-label {
    color: #ff0000;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 1px;
    margin-bottom: 2px;
}
.ep-guest {
    color: #f0f0f0;
    font-size: 0.92rem;
    font-weight: 700;
    margin-bottom: 8px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.ep-stats {
    display: flex;
    gap: 8px;
    font-size: 0.75rem;
    color: #888;
}
.ep-stats span { display: flex; align-items: center; gap: 3px; }

.comment-card {
    background: #1a1a1a;
    border-left: 3px solid #ff0000;
    border-radius: 6px;
    padding: 0.6rem 0.9rem;
    margin-bottom: 0.5rem;
    font-size: 0.88rem;
}
.comment-author { color: #ff4444; font-weight: 600; font-size: 0.8rem; margin-bottom: 2px; }
.comment-date { color: #555; font-size: 0.72rem; float: right; }
.info-banner {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    color: #aaa;
    font-size: 0.88rem;
}
</style>
""", unsafe_allow_html=True)

REFRESH_INTERVAL = 10 * 60
YT_API = "https://www.googleapis.com/youtube/v3"

def format_number(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n:,}"
    return str(n)


def parse_ep_guest(title):
    """제목에서 EP번호와 게스트명 파싱
    예: '어쩌구 저쩌구 | 입금 바랍니다 EP3 기리고'
    """
    match = re.search(r'EP\s*(\d+)\s+(.+?)(?:\s*\|.*)?$', title, re.IGNORECASE)
    if match:
        ep_num = match.group(1)
        guest = match.group(2).strip()
        return f"EP{ep_num}", guest
    # 파이프 앞부분에서 EP 찾기
    match2 = re.search(r'EP\s*(\d+)', title, re.IGNORECASE)
    if match2:
        ep_num = match2.group(1)
        # 파이프 뒤에서 게스트 추출
        pipe_match = re.search(r'\|\s*입금 바랍니다\s+EP\d+\s+(.+)', title, re.IGNORECASE)
        if pipe_match:
            return f"EP{ep_num}", pipe_match.group(1).strip()
        return f"EP{ep_num}", "게스트"
    return "EP?", title[:20]


def yt_get(endpoint, api_key, **params):
    resp = requests.get(
        f"{YT_API}/{endpoint}",
        params={"key": api_key, **params},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=REFRESH_INTERVAL, show_spinner=False)
def fetch_playlist_videos(api_key, playlist_id):
    videos = []
    next_page_token = None
    while True:
        data = yt_get("playlistItems", api_key,
                      part="snippet", playlistId=playlist_id,
                      maxResults=50, pageToken=next_page_token or "")
        for item in data.get("items", []):
            sn = item["snippet"]
            vid = sn["resourceId"]["videoId"]
            videos.append({
                "videoId": vid,
                "title": sn["title"],
                "thumbnail": sn.get("thumbnails", {}).get("medium", {}).get("url", ""),
            })
        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break
    return videos


@st.cache_data(ttl=REFRESH_INTERVAL, show_spinner=False)
def fetch_video_stats(api_key, video_ids):
    stats = {}
    ids = list(video_ids)
    for i in range(0, len(ids), 50):
        chunk = ids[i:i+50]
        data = yt_get("videos", api_key, part="statistics", id=",".join(chunk))
        for item in data.get("items", []):
            s = item.get("statistics", {})
            stats[item["id"]] = {
                "views": int(s.get("viewCount", 0)),
                "likes": int(s.get("likeCount", 0)),
                "comments": int(s.get("commentCount", 0)),
            }
    return stats


@st.cache_data(ttl=REFRESH_INTERVAL, show_spinner=False)
def fetch_recent_comments(api_key, video_id, max_results=5):
    try:
        data = yt_get("commentThreads", api_key,
                      part="snippet", videoId=video_id,
                      order="time", maxResults=max_results,
                      textFormat="plainText")
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code in (403, 400):
            return []
        raise
    comments = []
    for item in data.get("items", []):
        top = item["snippet"]["topLevelComment"]["snippet"]
        comments.append({
            "author": top.get("authorDisplayName", ""),
            "text": top.get("textDisplay", ""),
            "published_at": top.get("publishedAt", ""),
            "likes": top.get("likeCount", 0),
        })
    return comments
    
def has_new_comment(comments):
    """앱 실행 시점 기준 1시간 내 새 댓글 여부"""
    now = datetime.datetime.now(datetime.timezone.utc)
    for c in comments:
        try:
            dt = datetime.datetime.fromisoformat(c["published_at"].replace("Z", "+00:00"))
            if (now - dt).total_seconds() < 3600:
                return True
        except:
            pass
    return False

def format_dt(iso):
    try:
        dt = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%Y.%m.%d %H:%M")
    except Exception:
        return iso


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ 설정")
    st.markdown("---")
    api_key = st.secrets["YOUTUBE_API_KEY"]
    playlist_id = st.secrets["PLAYLIST_ID"]
    fetch_btn = st.button("🔄  새로고침", use_container_width=True)
    st.markdown("---")
    st.markdown("<div class='info-banner'>📡 데이터는 <b>10분마다</b> 자동으로 새로고침됩니다.</div>", unsafe_allow_html=True)
    if "last_fetch" in st.session_state:
        elapsed = time.time() - st.session_state["last_fetch"]
        remaining = max(0, REFRESH_INTERVAL - elapsed)
        mins, secs = divmod(int(remaining), 60)
        st.markdown(f"\n⏱ 다음 자동 새로고침: **{mins:02d}:{secs:02d}**")
    st.markdown("<br>", unsafe_allow_html=True)
    st.caption("입금 바랍니다 © 2025")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("<h1>▶ 입금 바랍니다 <span class='live-badge'>LIVE</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#666; margin-top:-0.5rem;'>입금 바랍니다 퍼포먼스 대시보드</p>", unsafe_allow_html=True)
st.markdown("---")

if fetch_btn:
    st.cache_data.clear()
    st.session_state["last_fetch"] = time.time()

if "last_fetch" not in st.session_state:
    st.session_state["last_fetch"] = time.time()
else:
    elapsed = time.time() - st.session_state["last_fetch"]
    if elapsed >= REFRESH_INTERVAL:
        st.cache_data.clear()
        st.session_state["last_fetch"] = time.time()
        st.rerun()

# ── Fetch ─────────────────────────────────────────────────────────────────────
try:
    with st.spinner("재생목록 불러오는 중..."):
        videos = fetch_playlist_videos(api_key, playlist_id)
except requests.HTTPError as e:
    st.error(f"API 오류: {e.response.status_code}")
    st.stop()
except Exception as e:
    st.error(f"오류 발생: {e}")
    st.stop()

if not videos:
    st.warning("재생목록에 영상이 없거나 비공개 재생목록입니다.")
    st.stop()

video_ids = tuple(v["videoId"] for v in videos)
with st.spinner("영상 통계 불러오는 중..."):
    stats = fetch_video_stats(api_key, video_ids)

# EP번호 기준 최신순 정렬
def ep_sort_key(v):
    ep, _ = parse_ep_guest(v["title"])
    try:
        return -int(ep.replace("EP", ""))
    except:
        return 0

videos_sorted = sorted(videos, key=ep_sort_key)

# ── 가로 스크롤 카드 ───────────────────────────────────────────────────────────
st.markdown("### 📺 회차별 현황")

if "selected_video" not in st.session_state:
    st.session_state["selected_video"] = None

# 카드 HTML 생성
cards_html = "<div class='scroll-wrapper'><div class='card-row'>"
for v in videos_sorted:
    ep_label, guest = parse_ep_guest(v["title"])
    s = stats.get(v["videoId"], {})
    views = format_number(s.get("views", 0))
    likes = format_number(s.get("likes", 0))
    comments = format_number(s.get("comments", 0))
    thumb = v["thumbnail"]
    cards_html += f"""
    <div class='ep-card'>
        <img src='{thumb}' alt='{guest}'>
        <div class='ep-card-body'>
            <div class='ep-label'>{ep_label}</div>
            <div class='ep-guest'>{guest}</div>
            <div class='ep-stats'>
                <span>▶️ {views}</span>
                <span>👍 {likes}</span>
                <span>💬 {comments}</span>
            </div>
        </div>
    </div>"""
cards_html += "</div></div>"

st.markdown(cards_html, unsafe_allow_html=True)

st.markdown("---")

# ── 통합 최신 댓글 ─────────────────────────────────────────────────────────────
st.markdown("### 🔔 전체 최신 댓글")

all_comments = []
for v in videos_sorted:
    ep_label, guest = parse_ep_guest(v["title"])
    comments = fetch_recent_comments(api_key, v["videoId"], max_results=10)
    for c in comments:
        c["ep_label"] = ep_label
        c["guest"] = guest
        all_comments.append(c)

# 시간순 정렬
def comment_dt(c):
    try:
        return datetime.datetime.fromisoformat(c["published_at"].replace("Z", "+00:00"))
    except:
        return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)

all_comments.sort(key=comment_dt, reverse=True)
top5 = all_comments[:5]

KST = datetime.timezone(datetime.timedelta(hours=9))
now_kst = datetime.datetime.now(KST)

for c in top5:
    try:
        dt = datetime.datetime.fromisoformat(c["published_at"].replace("Z", "+00:00")).astimezone(KST)
        is_new = (now_kst - dt).total_seconds() < 3600
        dt_str = dt.strftime("%Y.%m.%d %H:%M")
    except:
        is_new = False
        dt_str = c["published_at"]

    new_dot = "<span style='color:#ff0000; font-size:0.7rem; font-weight:700; margin-left:4px;'>● NEW</span>" if is_new else ""
    ep_tag = f"<span style='background:#ff0000; color:#fff; font-size:0.68rem; font-weight:700; padding:1px 7px; border-radius:4px; margin-right:6px;'>{c['ep_label']} {c['guest']}</span>"
    likes_html = f"<div style='color:#555; font-size:0.75rem; margin-top:4px;'>👍 {c['likes']}</div>" if c["likes"] > 0 else ""

    st.markdown(f"<div class='comment-card'><div class='comment-author'>{ep_tag}{c['author']}{new_dot}<span class='comment-date'>{dt_str}</span></div><div style='margin-top:4px;'>{c['text']}</div>{likes_html}</div>", unsafe_allow_html=True)

st.markdown("---")

# ── 댓글 토글 ─────────────────────────────────────────────────────────────────
st.markdown("### 💬 회차별 최근 댓글")
for v in videos_sorted:
    ep_label, guest = parse_ep_guest(v["title"])
    s = stats.get(v["videoId"], {})
    
    comments = fetch_recent_comments(api_key, v["videoId"], max_results=5)
    new_badge = " 🔴 N" if has_new_comment(comments) else ""
    
    label = f"**{ep_label} {guest}**{new_badge}  \n▶️ {format_number(s.get('views',0))} · 👍 {format_number(s.get('likes',0))} · 💬 {format_number(s.get('comments',0))}"
    
    with st.expander(label, expanded=False):
        if not comments:
            st.markdown("<p style='color:#555; font-size:0.85rem;'>댓글이 없거나 비활성화된 영상입니다.</p>", unsafe_allow_html=True)
        else:
            for c in comments:
                is_new = False
                try:
                    dt = datetime.datetime.fromisoformat(c["published_at"].replace("Z", "+00:00"))
                    is_new = (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds() < 3600
                except:
                    pass
                
                new_dot = "<span style='color:#ff0000; font-size:0.7rem; font-weight:700; margin-left:4px;'>● NEW</span>" if is_new else ""
                likes_html = f"<div style='color:#555; font-size:0.75rem; margin-top:4px;'>👍 {c['likes']}</div>" if c["likes"] > 0 else ""
                st.markdown(f"<div class='comment-card'><div class='comment-author'>{c['author']}{new_dot}<span class='comment-date'>{format_dt(c['published_at'])}</span></div><div style='margin-top:4px;'>{c['text']}</div>{likes_html}</div>", unsafe_allow_html=True)

# ── 퍼포먼스 트래킹 ─────────────────────────────────────────────────────────────
st.markdown("### 🎯 퍼포먼스 트래킹")

TOTAL_EP = 8
GOAL_PER_EP = 2_000_000
TOTAL_GOAL = TOTAL_EP * GOAL_PER_EP  # 16M

current_ep_count = len(videos)
total_views = sum(s.get("views", 0) for s in stats.values())
avg_views = total_views / current_ep_count if current_ep_count else 0
remaining_ep = TOTAL_EP - current_ep_count
needed_per_ep = (TOTAL_GOAL - total_views) / remaining_ep if remaining_ep > 0 else 0
projected_total = avg_views * TOTAL_EP
achievement_rate = total_views / TOTAL_GOAL * 100

# 상단 지표
c1, c2, c3 = st.columns(3)
c1.metric("📹 발행 에피소드", f"{current_ep_count} / {TOTAL_EP}화")
c2.metric("👁 누적 조회수", format_number(total_views))
c3.metric("🎯 목표까지 남은 조회수", format_number(max(0, TOTAL_GOAL - total_views)))

c4, c5, c6 = st.columns(3)
c4.metric("📊 회차별 평균 조회수", format_number(int(avg_views)))
c5.metric("🚀 남은 회차당 필요 조회수", format_number(int(needed_per_ep)))
c6.metric("📈 현재 페이스 예상 최종 조회수", format_number(int(projected_total)))

# 달성률 진행바
st.markdown(f"""
<div style='margin: 20px 0 8px;'>
    <div style='display:flex; justify-content:space-between; color:#888; font-size:0.8rem; margin-bottom:6px;'>
        <span>전체 목표 달성률</span>
        <span>{achievement_rate:.1f}% / 100%</span>
    </div>
    <div style='background:#1a1a1a; border-radius:8px; height:16px; overflow:hidden;'>
        <div style='background: linear-gradient(90deg, #ff0000, #ff4444); height:100%; width:{min(achievement_rate, 100):.1f}%; border-radius:8px; transition: width 0.5s;'></div>
    </div>
    <div style='display:flex; justify-content:space-between; color:#555; font-size:0.75rem; margin-top:4px;'>
        <span>0</span>
        <span>목표 16M</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# EP별 목표 대비 달성 현황
st.markdown("#### 회차별 2M 목표 달성 현황")

for v in videos_sorted:
    ep_label, guest = parse_ep_guest(v["title"])
    s = stats.get(v["videoId"], {})
    views = s.get("views", 0)
    rate = min(views / GOAL_PER_EP * 100, 100)
    color = "#00cc66" if views >= GOAL_PER_EP else "#ff0000"
    status = "✅ 달성" if views >= GOAL_PER_EP else f"{rate:.1f}%"

    st.markdown(f"""
    <div style='margin-bottom:12px;'>
        <div style='display:flex; justify-content:space-between; margin-bottom:4px;'>
            <span style='font-weight:700; color:#f0f0f0;'>{ep_label} {guest}</span>
           <span style='font-size:0.85rem;'><span style='color:#ffffff; font-weight:700;'>{format_number(views)}</span> <span style='color:{color}; font-weight:700;'>{status}</span></span>
        </div>
        <div style='background:#1a1a1a; border-radius:6px; height:10px; overflow:hidden;'>
            <div style='background:{color}; height:100%; width:{rate:.1f}%; border-radius:6px;'></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# 페이스 분석 코멘트
st.markdown("<br>", unsafe_allow_html=True)
if projected_total >= TOTAL_GOAL:
    diff = projected_total - TOTAL_GOAL
    st.success(f"🚀 현재 페이스 유지 시 목표 **16M 초과 달성** 예상! (+{format_number(int(diff))})")
else:
    diff = TOTAL_GOAL - projected_total
    st.warning(f"⚠️ 현재 페이스 유지 시 목표까지 **{format_number(int(diff))} 부족** 예상. 남은 {remaining_ep}화에서 회차당 **{format_number(int(needed_per_ep))}** 필요!")

# ── Footer ────────────────────────────────────────────────────────────────────
KST = datetime.timezone(datetime.timedelta(hours=9))
now_kst = datetime.datetime.now(KST).strftime("%Y년 %m월 %d일 %H:%M:%S KST")
st.markdown(f"<p style='color:#444; font-size:0.78rem; text-align:right;'>마지막 업데이트: {now_kst}</p>", unsafe_allow_html=True)
