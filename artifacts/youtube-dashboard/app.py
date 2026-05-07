import streamlit as st
import pandas as pd
import requests
import time
import datetime

st.set_page_config(
    page_title="입금 바랍니다 — 대시보드",
    page_icon="▶",
    layout="wide",
)

st.markdown(
    """
    <style>
    html, body, [data-testid="stApp"] {
        background-color: #0d0d0d;
        color: #e0e0e0;
    }
    [data-testid="stSidebar"] {
        background-color: #141414;
        border-right: 1px solid #222;
    }
    [data-testid="stSidebar"] label { color: #f0f0f0; }
    input[type="text"], input[type="password"], textarea {
        background-color: #1a1a1a !important;
        color: #e0e0e0 !important;
        border: 1px solid #333 !important;
        border-radius: 6px !important;
    }
    .stButton > button {
        background-color: #ff0000;
        color: #fff;
        border: none;
        border-radius: 6px;
        font-weight: 600;
        padding: 0.4rem 1.2rem;
    }
    .stButton > button:hover { background-color: #cc0000; color: #fff; }
    [data-testid="metric-container"] {
        background-color: #1a1a1a;
        border: 1px solid #2a2a2a;
        border-radius: 10px;
        padding: 1rem;
    }
    [data-testid="metric-container"] label { color: #888 !important; font-size: 0.8rem !important; }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #f0f0f0 !important;
        font-size: 1.6rem !important;
        font-weight: 700 !important;
    }
    [data-testid="stDataFrame"] { border: 1px solid #222; border-radius: 8px; overflow: hidden; }
    [data-testid="stExpander"] { background-color: #141414; border: 1px solid #222; border-radius: 8px; }
    hr { border-color: #2a2a2a; }
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
    """,
    unsafe_allow_html=True,
)

REFRESH_INTERVAL = 10 * 60
YT_API = "https://www.googleapis.com/youtube/v3"


def format_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def yt_get(endpoint: str, api_key: str, **params) -> dict:
    resp = requests.get(
        f"{YT_API}/{endpoint}",
        params={"key": api_key, **params},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=REFRESH_INTERVAL, show_spinner=False)
def fetch_playlist_videos(api_key: str, playlist_id: str):
    videos = []
    next_page_token = None
    while True:
        data = yt_get(
            "playlistItems",
            api_key,
            part="snippet",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token or "",
        )
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
def fetch_video_stats(api_key: str, video_ids: tuple):
    stats = {}
    ids = list(video_ids)
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
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
def fetch_recent_comments(api_key: str, video_id: str, max_results: int = 5):
    try:
        data = yt_get(
            "commentThreads",
            api_key,
            part="snippet",
            videoId=video_id,
            order="time",
            maxResults=max_results,
            textFormat="plainText",
        )
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


def format_dt(iso: str) -> str:
    try:
        dt = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%Y.%m.%d %H:%M")
    except Exception:
        return iso


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ 설정")
    st.markdown("---")
    api_key = st.text_input(
        "YouTube Data API v3 Key",
        type="password",
        placeholder="AIza...",
        help="Google Cloud Console에서 발급받은 API 키를 입력하세요.",
    )
    playlist_id = st.text_input(
        "Playlist ID",
        placeholder="PLxxxxxxxxxxxxxxxx",
        help="유튜브 재생목록 URL의 'list=' 뒤에 오는 값입니다.",
    )
    fetch_btn = st.button("🔄  데이터 불러오기", use_container_width=True)
    st.markdown("---")
    st.markdown(
        "<div class='info-banner'>📡 데이터는 <b>10분마다</b> 자동으로 새로고침됩니다.</div>",
        unsafe_allow_html=True,
    )
    if "last_fetch" in st.session_state:
        elapsed = time.time() - st.session_state["last_fetch"]
        remaining = max(0, REFRESH_INTERVAL - elapsed)
        mins, secs = divmod(int(remaining), 60)
        st.markdown(f"\n⏱ 다음 자동 새로고침: **{mins:02d}:{secs:02d}**")
    st.markdown("<br>", unsafe_allow_html=True)
    st.caption("입금 바랍니다 © 2025")

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown(
    "<h1>▶ 입금 바랍니다 <span class='live-badge'>LIVE</span></h1>",
    unsafe_allow_html=True,
)
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

if not api_key or not playlist_id:
    st.markdown(
        """
        <div class='info-banner' style='text-align:center; padding: 2rem;'>
            <h3 style='color:#e0e0e0; margin-bottom:0.5rem;'>👈 사이드바에서 설정을 입력해주세요</h3>
            <p style='color:#666;'>YouTube API Key와 Playlist ID를 입력한 뒤<br>
            <b>데이터 불러오기</b> 버튼을 누르면 대시보드가 시작됩니다.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# ── Fetch ─────────────────────────────────────────────────────────────────────

try:
    with st.spinner("재생목록 불러오는 중..."):
        videos = fetch_playlist_videos(api_key, playlist_id)
except requests.HTTPError as e:
    st.error(f"API 오류: {e.response.status_code} — {e.response.text[:200]}")
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

# ── Metrics ───────────────────────────────────────────────────────────────────

total_views = sum(s.get("views", 0) for s in stats.values())
total_likes = sum(s.get("likes", 0) for s in stats.values())
total_comments = sum(s.get("comments", 0) for s in stats.values())

c1, c2, c3, c4 = st.columns(4)
c1.metric("📹 총 영상 수", f"{len(videos)}개")
c2.metric("👁 누적 조회수", format_number(total_views))
c3.metric("👍 누적 좋아요", format_number(total_likes))
c4.metric("💬 누적 댓글 수", format_number(total_comments))

st.markdown("---")

# ── Table ─────────────────────────────────────────────────────────────────────

st.markdown("### 📊 영상별 성과 현황")

rows = []
for v in videos:
    s = stats.get(v["videoId"], {})
    rows.append({
        "제목": v["title"],
        "조회수": s.get("views", 0),
        "좋아요": s.get("likes", 0),
        "댓글 수": s.get("comments", 0),
        "링크": f"https://www.youtube.com/watch?v={v['videoId']}",
    })

df = pd.DataFrame(rows)
df_display = df.copy()
for col in ["조회수", "좋아요", "댓글 수"]:
    df_display[col] = df_display[col].apply(format_number)

st.dataframe(
    df_display[["제목", "조회수", "좋아요", "댓글 수", "링크"]],
    use_container_width=True,
    hide_index=True,
    column_config={"링크": st.column_config.LinkColumn("링크", display_text="▶ 보기")},
)

st.markdown("---")

# ── Comments ──────────────────────────────────────────────────────────────────

st.markdown("### 💬 영상별 최근 댓글 (최신 5개)")

for v in videos:
    with st.expander(f"**{v['title']}**", expanded=False):
        with st.spinner("댓글 불러오는 중..."):
            comments = fetch_recent_comments(api_key, v["videoId"], max_results=5)
        if not comments:
            st.markdown(
                "<p style='color:#555; font-size:0.85rem;'>댓글이 없거나 비활성화된 영상입니다.</p>",
                unsafe_allow_html=True,
            )
        else:
            for c in comments:
                likes_html = f"<div style='color:#555; font-size:0.75rem; margin-top:4px;'>👍 {c['likes']}</div>" if c["likes"] > 0 else ""
                st.markdown(
                    f"""<div class='comment-card'>
                        <div class='comment-author'>{c['author']}
                            <span class='comment-date'>{format_dt(c['published_at'])}</span>
                        </div>
                        <div style='margin-top:4px;'>{c['text']}</div>
                        {likes_html}
                    </div>""",
                    unsafe_allow_html=True,
                )

# ── Footer ────────────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown(
    f"<p style='color:#444; font-size:0.78rem; text-align:right;'>마지막 업데이트: {datetime.datetime.now().strftime('%Y년 %m월 %d일 %H:%M:%S')}</p>",
    unsafe_allow_html=True,
)

time.sleep(1)
st.rerun()
