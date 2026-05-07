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
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def parse_ep_guest(title):
    """제목에서 EP번호와 게스트명 파싱
    예: '어쩌구 저쩌구 | 입금 바랍니다 EP3 기리보이'
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
st.markdown("<p style='color:#666; margin-top:-0.5rem;'>웹시리즈 성과 관리 대시보드</p>", unsafe_allow_html=True)
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
                <span>👁 {views}</span>
                <span>👍 {likes}</span>
                <span>💬 {comments}</span>
            </div>
        </div>
    </div>"""
cards_html += "</div></div>"

st.markdown(cards_html, unsafe_allow_html=True)

st.markdown("---")

# ── 댓글 토글 ─────────────────────────────────────────────────────────────────
st.markdown("### 💬 회차별 최근 댓글")

for v in videos_sorted:
    ep_label, guest = parse_ep_guest(v["title"])
    s = stats.get(v["videoId"], {})
    label = f"**{ep_label} {guest}** · 👁 {format_number(s.get('views',0))} · 👍 {format_number(s.get('likes',0))} · 💬 {format_number(s.get('comments',0))}"
    with st.expander(label, expanded=False):
        with st.spinner("댓글 불러오는 중..."):
            comments = fetch_recent_comments(api_key, v["videoId"], max_results=5)
        if not comments:
            st.markdown("<p style='color:#555; font-size:0.85rem;'>댓글이 없거나 비활성화된 영상입니다.</p>", unsafe_allow_html=True)
        else:
            for c in comments:
                likes_html = f"<div style='color:#555; font-size:0.75rem; margin-top:4px;'>👍 {c['likes']}</div>" if c["likes"] > 0 else ""
                st.markdown(f"""<div class='comment-card'>
                    <div class='comment-author'>{c['author']}
                        <span class='comment-date'>{format_dt(c['published_at'])}</span>
                    </div>
                    <div style='margin-top:4px;'>{c['text']}</div>
                    {likes_html}
                </div>""", unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(f"<p style='color:#444; font-size:0.78rem; text-align:right;'>마지막 업데이트: {datetime.datetime.now().strftime('%Y년 %m월 %d일 %H:%M:%S')}</p>", unsafe_allow_html=True)

time.sleep(1)
st.rerun()
