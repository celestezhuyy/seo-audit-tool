import streamlit as st
import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# --- 1. 页面基础配置 ---
st.set_page_config(
    page_title="NextGen SEO Auditor",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. 爬虫核心引擎 (真实逻辑) ---

def is_valid_url(url):
    """检查URL格式是否正确"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def analyze_page(url, html_content, status_code):
    """分析单个页面的SEO指标，返回数据和问题列表"""
    soup = BeautifulSoup(html_content, 'html.parser')
    issues = []
    
    # A. 标题分析
    title_tag = soup.title
    title = title_tag.string.strip() if title_tag and title_tag.string else None
    
    if not title:
        issues.append({
            "severity": "High",
            "title": "缺失页面标题 (Title Tag)",
            "desc": "页面没有 <title> 标签，搜索引擎无法理解页面主题。",
            "suggestion": "在 <head> 中添加描述性的标题。",
            "url": url
        })
    elif len(title) < 10:
         issues.append({
            "severity": "Medium",
            "title": "标题过短",
            "desc": f"标题仅有 {len(title)} 个字符，难以覆盖核心关键词。",
            "suggestion": "建议将标题扩充至 30-60 个字符。",
            "url": url
        })

    # B. H1 分析
    h1 = soup.find('h1')
    h1_text = h1.get_text().strip() if h1 else "No H1"
    
    if not h1:
        issues.append({
            "severity": "High",
            "title": "缺失 H1 标签",
            "desc": "页面缺乏主标题 (H1)，影响页面层级结构。",
            "suggestion": "添加且仅添加一个包含核心关键词的 H1 标签。",
            "url": url
        })

    # C. 软 404 检测 (简单的关键词匹配)
    text_content = soup.get_text().lower()
    if status_code == 200 and ("page not found" in text_content or "404 error" in text_content):
        issues.append({
            "severity": "Critical",
            "title": "疑似软 404 (Soft 404)",
            "desc": "页面返回 200 状态码，但内容显示'未找到'。",
            "suggestion": "配置服务器，对不存在的页面返回真正的 404 状态码。",
            "url": url
        })
        
    # D. 图片 Alt 属性检测
    images = soup.find_all('img')
    missing_alt = 0
    for img in images:
        if not img.get('alt'):
            missing_alt += 1
    if missing_alt > 0:
        issues.append({
            "severity": "Medium",
            "title": "图片缺失 Alt 属性", # 统一 Title 以便聚合
            "desc": "图片缺少替代文本，影响图片搜索排名和无障碍访问。",
            "suggestion": "为所有 img 标签添加描述性的 alt 属性。",
            "url": url,
            "meta": f"该页面有 {missing_alt} 张图片缺失 Alt" # 额外信息
        })

    # E. 提取内部链接 (用于继续爬取)
    internal_links = set()
    base_domain = urlparse(url).netloc
    for a in soup.find_all('a', href=True):
        link = urljoin(url, a['href'])
        parsed_link = urlparse(link)
        # 只收集同一域名下的链接，防止爬出去
        if parsed_link.netloc == base_domain:
            # 过滤掉图片、PDF等非HTML链接
            if not any(link.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.pdf', '.css', '.js']):
                internal_links.add(link)

    return {
        "URL": url,
        "Status": status_code,
        "Title": title or "No Title",
        "H1": h1_text,
        "Links_Count": len(internal_links),
        "Issues_Count": len(issues)
    }, issues, internal_links

def crawl_website(start_url, max_pages=100):
    """执行广度优先爬取"""
    visited = set()
    queue = [start_url]
    results_data = []
    all_issues = []
    
    # 界面上的进度条
    progress_bar = st.progress(0, text="初始化爬虫引擎...")
    status_text = st.empty()
    
    pages_crawled = 0
    
    while queue and pages_crawled < max_pages:
        url = queue.pop(0)
        
        # 去重处理
        if url in visited:
            continue
        visited.add(url)
        
        pages_crawled += 1
        
        # 更新进度显示
        progress = int((pages_crawled / max_pages) * 100)
        progress_bar.progress(progress, text=f"正在爬取 ({pages_crawled}/{max_pages}): {url}")
        
        try:
            # 模拟浏览器 User-Agent
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(url, headers=headers, timeout=10)
            
            # 确保是 HTML 页面
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' in content_type:
                page_data, page_issues, new_links = analyze_page(url, response.content, response.status_code)
                
                results_data.append(page_data)
                all_issues.extend(page_issues)
                
                # 将新发现的链接加入队列
                for link in new_links:
                    if link not in visited and link not in queue:
                        queue.append(link)
            else:
                pass # 忽略非 HTML 文件

        except Exception as e:
            # 记录错误但不中断程序
            st.toast(f"无法访问 {url}: {str(e)}")
    
    progress_bar.progress(100, text="分析完成！正在生成报告...")
    time.sleep(0.5)
    progress_bar.empty()
    
    return results_data, all_issues

# --- 3. 初始化 Session State (缓存数据) ---
if 'audit_data' not in st.session_state:
    st.session_state['audit_data'] = None
if 'audit_issues' not in st.session_state:
    st.session_state['audit_issues'] = []

# --- 4. 侧边栏导航 ---
with st.sidebar:
    st.title("🔍 AuditAI Pro")
    st.caption("Live Crawler Edition")
    
    menu = st.radio(
        "功能导航",
        ["输入网址", "仪表盘", "数据矩阵", "PPT 生成器"]
    )
    
    st.divider()
    if st.session_state['audit_data'] is not None:
        st.success(f"已缓存 {len(st.session_state['audit_data'])} 个页面")
        if st.button("清除数据并重置"):
            st.session_state['audit_data'] = None
            st.session_state['audit_issues'] = []
            st.rerun()

# --- 5. 主界面逻辑 ---

if menu == "输入网址":
    st.header("开始新的审计")
    st.info("说明: 这是一个真实爬虫。输入网址后，系统将实时访问该网站并分析前 100 个页面。")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        url_input = st.text_input("输入目标网址 (例如 https://example.com)", placeholder="https://...")
    with col2:
        start_btn = st.button("开始真实爬取", type="primary", use_container_width=True)
    
    if start_btn and url_input:
        if not is_valid_url(url_input):
            st.error("网址格式错误，请确保包含 http:// 或 https://")
        else:
            with st.spinner("正在启动爬虫，爬取 100 个页面可能需要 1-2 分钟，请耐心等待..."):
                # 这里修改为 100 页
                data, issues = crawl_website(url_input, max_pages=100)
                
                if not data:
                    st.error("未能爬取到任何页面，请检查网址是否可访问，或网站是否有反爬虫机制。")
                else:
                    # 存入 Session State
                    st.session_state['audit_data'] = data
                    st.session_state['audit_issues'] = issues
                    st.success(f"审计完成！共分析 {len(data)} 个页面，发现 {len(issues)} 个问题。")
                    st.balloons()

elif menu == "仪表盘":
    st.header("执行摘要 (Executive Summary)")
    
    if st.session_state['audit_data'] is None:
        st.warning("暂无数据，请先前往'输入网址'页面进行爬取。")
    else:
        df = pd.DataFrame(st.session_state['audit_data'])
        issues = st.session_state['audit_issues']
        
        # 计算健康度 (模拟算法)
        total_issues = len(issues)
        health_score = max(0, 100 - int(total_issues * 0.5)) # 降低扣分权重因为页面多了
        
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("网站健康度", f"{health_score}/100")
        kpi2.metric("已分析页面", str(len(df)))
        kpi3.metric("发现问题总数", str(total_issues), delta_color="inverse")
        
        critical_count = len([i for i in issues if i['severity'] == 'Critical'])
        kpi4.metric("严重问题 (Critical)", str(critical_count), delta_color="inverse")
        
        st.divider()
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("问题类型分布")
            if issues:
                issue_types = pd.DataFrame(issues)['title'].value_counts()
                st.bar_chart(issue_types)
            else:
                st.info("未发现明显问题。")
                
        with col2:
            st.subheader("HTTP 状态码分布")
            if not df.empty:
                status_counts = df['Status'].value_counts()
                st.bar_chart(status_counts)

elif menu == "数据矩阵":
    st.header("全站数据明细 (Big Sheet)")
    
    if st.session_state['audit_data'] is None:
        st.warning("暂无数据，请先爬取。")
    else:
        df = pd.DataFrame(st.session_state['audit_data'])
        
        st.dataframe(
            df,
            column_config={
                "URL": st.column_config.LinkColumn("Page URL"),
                "Status": st.column_config.NumberColumn("Status Code", format="%d"),
            },
            use_container_width=True,
            hide_index=True
        )
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("下载 CSV 报告", csv, "audit_report.csv", "text/csv")

elif menu == "PPT 生成器":
    st.header("演示文稿预览 (Pitch Deck Mode)")
    
    if st.session_state['audit_data'] is None:
        st.warning("暂无数据，无法生成 PPT。")
    elif not st.session_state['audit_issues']:
        st.success("恭喜！未发现严重问题，无需生成修复建议 PPT。")
    else:
        # --- 聚合逻辑开始 ---
        raw_issues = st.session_state['audit_issues']
        grouped_issues = {}
        
        for issue in raw_issues:
            title = issue['title']
            if title not in grouped_issues:
                # 初始化该类问题
                grouped_issues[title] = {
                    "title": title,
                    "severity": issue['severity'],
                    "desc": issue['desc'],
                    "suggestion": issue['suggestion'],
                    "count": 0,
                    "examples": [], # 存储受影响的URL
                    "meta": issue.get('meta', '') # 额外信息
                }
            
            grouped_issues[title]['count'] += 1
            if len(grouped_issues[title]['examples']) < 3: # 只存前3个例子
                grouped_issues[title]['examples'].append(issue['url'])
        
        # 将字典转换为列表，并按严重程度排序 (Critical > High > Medium)
        severity_order = {"Critical": 0, "High": 1, "Medium": 2}
        ppt_slides = sorted(
            list(grouped_issues.values()), 
            key=lambda x: (severity_order.get(x['severity'], 3), -x['count'])
        )
        # --- 聚合逻辑结束 ---

        st.caption(f"系统已自动聚合相同类型的问题，共生成 {len(ppt_slides)} 张关键幻灯片。")
        
        if 'slide_index' not in st.session_state:
            st.session_state.slide_index = 0
            
        # 防止索引越界
        if st.session_state.slide_index >= len(ppt_slides):
            st.session_state.slide_index = 0
            
        slide = ppt_slides[st.session_state.slide_index]
        
        # 模拟 PPT 框架 (16:9)
        with st.container(border=True):
            # 标题区域展示统计数据
            st.markdown(f"### 问题类型: {slide['title']}")
            
            c1, c2 = st.columns([1, 1])
            with c1:
                color = "red" if slide['severity'] == "Critical" else "orange" if slide['severity'] == "High" else "blue"
                st.markdown(f"**严重程度:** :{color}[{slide['severity']}]")
                st.markdown(f"**影响范围:** 全站共发现 **{slide['count']}** 个页面存在此问题。")
                
                st.markdown("**问题描述:**")
                st.write(slide['desc'])
                
                st.info(f"💡 **修复建议:** {slide['suggestion']}")
            
            with c2:
                # 展示示例 URL 列表
                st.markdown("**🔍 受影响页面示例:**")
                for ex_url in slide['examples']:
                    st.markdown(f"- `{ex_url}`")
                if slide['count'] > 3:
                    st.caption(f"...以及其他 {slide['count'] - 3} 个页面。")
                    
                st.markdown("---")
                # 截图占位符
                st.image("https://placehold.co/600x300/EEE/31343C?text=Screenshot+Example", caption="请截取上述示例页面之一作为证据")

        # 翻页按钮
        col_prev, col_info, col_next = st.columns([1, 2, 1])
        with col_prev:
            if st.button("⬅️ 上一页"):
                if st.session_state.slide_index > 0:
                    st.session_state.slide_index -= 1
                    st.rerun()
        with col_info:
            st.markdown(f"<div style='text-align: center'>Slide {st.session_state.slide_index + 1} / {len(ppt_slides)}</div>", unsafe_allow_html=True)
        with col_next:
            if st.button("下一页 ➡️"):
                if st.session_state.slide_index < len(ppt_slides) - 1:
                    st.session_state.slide_index += 1
                    st.rerun()
