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

def check_site_level_assets(start_url):
    """检查站点级别的 SEO 资产 (Robots.txt, Sitemap)"""
    issues = []
    parsed_url = urlparse(start_url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    # 1. Robots.txt 检查
    robots_url = urljoin(base_url, "/robots.txt")
    try:
        r = requests.head(robots_url, timeout=5)
        if r.status_code != 200:
            issues.append({
                "severity": "Medium",
                "title": "缺失 Robots.txt",
                "desc": "无法在根目录找到 robots.txt 文件，可能导致爬取控制混乱。",
                "suggestion": "在网站根目录创建 robots.txt 文件以指导爬虫。",
                "url": robots_url,
                "meta": f"Status: {r.status_code}"
            })
    except:
        pass # 网络错误忽略

    # 2. Sitemap.xml 检查 (简单检查根目录)
    sitemap_url = urljoin(base_url, "/sitemap.xml")
    try:
        r = requests.head(sitemap_url, timeout=5)
        if r.status_code != 200:
             # 有些网站Sitemap不在根目录，这里给个低优先级的提示
            issues.append({
                "severity": "Low",
                "title": "根目录未发现 Sitemap.xml",
                "desc": "根目录无 sitemap.xml。如果您的 Sitemap 位于其他位置，请确保在 robots.txt 中声明。",
                "suggestion": "确保 Sitemap 可访问并在 robots.txt 中引用。",
                "url": sitemap_url,
                "meta": f"Status: {r.status_code}"
            })
    except:
        pass

    return issues

def analyze_page(url, html_content, status_code):
    """分析单个页面的SEO指标，返回数据和问题列表"""
    soup = BeautifulSoup(html_content, 'html.parser')
    issues = []
    
    # --- A. 基础内容检查 ---
    
    # 1. 标题 (Title)
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
    elif len(title) > 60:
         issues.append({
            "severity": "Low",
            "title": "标题过长",
            "desc": f"标题长达 {len(title)} 字符，在搜索结果中可能会被截断。",
            "suggestion": "建议将标题控制在 60 个字符以内。",
            "url": url
        })

    # 2. 元描述 (Meta Description)
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    desc_content = meta_desc['content'].strip() if meta_desc and meta_desc.get('content') else None
    
    if not desc_content:
        issues.append({
            "severity": "High",
            "title": "缺失元描述 (Meta Description)",
            "desc": "缺失元描述会降低搜索结果的点击率 (CTR)。",
            "suggestion": "添加 <meta name='description'> 标签，概括页面内容。",
            "url": url
        })
    elif len(desc_content) < 50:
        issues.append({
            "severity": "Low",
            "title": "元描述过短",
            "desc": "描述内容太少，无法有效吸引用户点击。",
            "suggestion": "建议扩充至 120-160 个字符。",
            "url": url
        })

    # 3. H1 标签
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

    # --- B. 技术与代码检查 ---

    # 4. 移动端视口 (Mobile Viewport)
    viewport = soup.find('meta', attrs={'name': 'viewport'})
    if not viewport:
        issues.append({
            "severity": "Critical",
            "title": "缺失移动端视口配置",
            "desc": "页面未配置 Viewport Meta 标签，Google 可能不会将其视为移动友好页面。",
            "suggestion": "添加 <meta name='viewport' content='width=device-width, initial-scale=1'>。",
            "url": url
        })

    # 5. 规范标签 (Canonical)
    canonical = soup.find('link', attrs={'rel': 'canonical'})
    if not canonical:
        issues.append({
            "severity": "Medium",
            "title": "缺失规范标签 (Canonical)",
            "desc": "未指定规范链接，可能导致参数不同的同一页面被视为重复内容。",
            "suggestion": "添加 <link rel='canonical' href='...' /> 指向当前页面的标准 URL。",
            "url": url
        })

    # 6. Favicon (网站图标)
    # 检查 link rel="icon" 或 "shortcut icon"
    favicon = soup.find('link', rel=lambda x: x and 'icon' in x.lower())
    if not favicon:
         issues.append({
            "severity": "Low",
            "title": "缺失 Favicon (网站图标)",
            "desc": "未检测到 Favicon 设置。这会影响在搜索结果页(SERP)中的品牌展示。",
            "suggestion": "在 <head> 中添加 <link rel='icon' href='...'>。",
            "url": url
        })

    # 7. 结构化数据 (Structured Data / Schema)
    # Google 推荐使用 JSON-LD
    schema = soup.find('script', type='application/ld+json')
    if not schema:
         issues.append({
            "severity": "Medium",
            "title": "未检测到结构化数据 (JSON-LD)",
            "desc": "结构化数据有助于 Google 理解内容并生成富媒体搜索结果 (Rich Snippets)。",
            "suggestion": "添加适合页面的 JSON-LD 结构化数据（如 Organization, Article, Product）。",
            "url": url
        })

    # 8. Hreflang (多语言支持)
    # 检查是否存在 hreflang 标签
    hreflang = soup.find('link', hreflang=True)
    if not hreflang:
        # 这里给一个低优先级的提示，因为并非所有网站都需要多语言
        issues.append({
            "severity": "Low",
            "title": "未发现 Hreflang 标记",
            "desc": "如果您针对不同地区/语言的用户提供内容，缺失 hreflang 会导致索引混乱。",
            "suggestion": "如果网站是多语言的，请添加 <link rel='alternate' hreflang='...' />。",
            "url": url
        })

    # --- C. URL 结构与爬取效率 ---

    # 9. URL 结构检查
    parsed_url = urlparse(url)
    path = parsed_url.path
    
    if '_' in path:
         issues.append({
            "severity": "Low",
            "title": "URL 包含下划线",
            "desc": "Google 建议在 URL 中使用连字符 (-) 而非下划线 (_) 分隔单词。",
            "suggestion": "优化 URL 结构，使用连字符代替下划线。",
            "url": url
        })
    
    if any(c.isupper() for c in path):
         issues.append({
            "severity": "Medium",
            "title": "URL 包含大写字母",
            "desc": "URL 是区分大小写的。混合大小写容易导致重复内容问题和外部链接错误。",
            "suggestion": "统一使用全小写字母的 URL。",
            "url": url
        })
    
    if len(url) > 100:
         issues.append({
            "severity": "Low",
            "title": "URL 过长",
            "desc": "过长的 URL 不利于用户阅读和分享，也可能被截断。",
            "suggestion": "保持 URL 简短且具有描述性。",
            "url": url
        })

    # 10. JavaScript 链接陷阱
    # 检查 href="javascript:..."
    js_links = soup.find_all('a', href=lambda x: x and x.lower().startswith('javascript:'))
    if js_links:
        issues.append({
            "severity": "High",
            "title": "发现 JavaScript 伪链接",
            "desc": f"发现 {len(js_links)} 个链接使用 href='javascript:'，爬虫无法跟踪此类链接。",
            "suggestion": "使用标准的 <a href='URL'> 标签，仅在 onclick 事件中使用 JS。",
            "url": url,
            "meta": f"Count: {len(js_links)}"
        })

    # --- D. 内容质量 ---

    # 11. 软 404 检测
    text_content = soup.get_text().lower()
    if status_code == 200 and ("page not found" in text_content or "404 error" in text_content):
        issues.append({
            "severity": "Critical",
            "title": "疑似软 404 (Soft 404)",
            "desc": "页面返回 200 状态码，但内容显示'未找到'。",
            "suggestion": "配置服务器，对不存在的页面返回真正的 404 状态码。",
            "url": url
        })
        
    # 12. 图片 Alt 属性
    images = soup.find_all('img')
    missing_alt = 0
    for img in images:
        if not img.get('alt'):
            missing_alt += 1
    if missing_alt > 0:
        issues.append({
            "severity": "Medium",
            "title": "图片缺失 Alt 属性",
            "desc": "图片缺少替代文本，影响图片搜索排名和无障碍访问。",
            "suggestion": "为所有 img 标签添加描述性的 alt 属性。",
            "url": url,
            "meta": f"该页面有 {missing_alt} 张图片缺失 Alt"
        })

    # E. 提取内部链接
    internal_links = set()
    base_domain = urlparse(url).netloc
    for a in soup.find_all('a', href=True):
        link = urljoin(url, a['href'])
        parsed_link = urlparse(link)
        if parsed_link.netloc == base_domain:
            # 过滤非HTML
            if not any(link.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.pdf', '.css', '.js', '.zip']):
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
    
    progress_bar = st.progress(0, text="初始化爬虫引擎...")
    
    # 0. 站点级检查 (执行一次)
    try:
        site_issues = check_site_level_assets(start_url)
        all_issues.extend(site_issues)
    except Exception as e:
        st.toast(f"站点级检查失败: {str(e)}")

    pages_crawled = 0
    
    while queue and pages_crawled < max_pages:
        url = queue.pop(0)
        
        if url in visited:
            continue
        visited.add(url)
        pages_crawled += 1
        
        progress = int((pages_crawled / max_pages) * 100)
        progress_bar.progress(progress, text=f"正在爬取 ({pages_crawled}/{max_pages}): {url}")
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (compatible; SEOAuditBot/1.0)'}
            response = requests.get(url, headers=headers, timeout=10)
            
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' in content_type:
                page_data, page_issues, new_links = analyze_page(url, response.content, response.status_code)
                results_data.append(page_data)
                all_issues.extend(page_issues)
                
                for link in new_links:
                    if link not in visited and link not in queue:
                        queue.append(link)
        except Exception as e:
            pass # 忽略单个页面错误
    
    progress_bar.progress(100, text="分析完成！")
    time.sleep(0.5)
    progress_bar.empty()
    
    return results_data, all_issues

# --- 3. 初始化 Session State ---
if 'audit_data' not in st.session_state:
    st.session_state['audit_data'] = None
if 'audit_issues' not in st.session_state:
    st.session_state['audit_issues'] = []

# --- 4. 侧边栏 ---
with st.sidebar:
    st.title("🔍 AuditAI Pro")
    st.caption("Live Crawler Edition v2.0")
    
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
    st.info("说明: 升级版爬虫，支持 Robots.txt、Sitemap、结构化数据及 URL 规范检查。")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        url_input = st.text_input("输入目标网址", placeholder="https://example.com")
    with col2:
        start_btn = st.button("开始真实爬取", type="primary", use_container_width=True)
    
    if start_btn and url_input:
        if not is_valid_url(url_input):
            st.error("网址格式错误")
        else:
            with st.spinner("正在启动爬虫 (Max 100 pages)..."):
                data, issues = crawl_website(url_input, max_pages=100)
                if not data:
                    st.error("未能爬取到任何页面。")
                else:
                    st.session_state['audit_data'] = data
                    st.session_state['audit_issues'] = issues
                    st.success(f"审计完成！共分析 {len(data)} 个页面。")
                    st.balloons()

elif menu == "仪表盘":
    st.header("执行摘要 (Executive Summary)")
    if st.session_state['audit_data'] is None:
        st.warning("暂无数据。")
    else:
        df = pd.DataFrame(st.session_state['audit_data'])
        issues = st.session_state['audit_issues']
        
        total_issues = len(issues)
        health_score = max(0, 100 - int(total_issues * 0.5))
        
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("网站健康度", f"{health_score}/100")
        kpi2.metric("已分析页面", str(len(df)))
        kpi3.metric("发现问题总数", str(total_issues), delta_color="inverse")
        critical_count = len([i for i in issues if i['severity'] == 'Critical'])
        kpi4.metric("严重问题", str(critical_count), delta_color="inverse")
        
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
        st.warning("暂无数据。")
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
        st.warning("暂无数据。")
    elif not st.session_state['audit_issues']:
        st.success("无严重问题。")
    else:
        # 聚合逻辑
        raw_issues = st.session_state['audit_issues']
        grouped_issues = {}
        for issue in raw_issues:
            title = issue['title']
            if title not in grouped_issues:
                grouped_issues[title] = {
                    "title": title, "severity": issue['severity'],
                    "desc": issue['desc'], "suggestion": issue['suggestion'],
                    "count": 0, "examples": [], "meta": issue.get('meta', '')
                }
            grouped_issues[title]['count'] += 1
            if len(grouped_issues[title]['examples']) < 3:
                grouped_issues[title]['examples'].append(issue['url'])
        
        severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        ppt_slides = sorted(list(grouped_issues.values()), key=lambda x: (severity_order.get(x['severity'], 3), -x['count']))

        if 'slide_index' not in st.session_state: st.session_state.slide_index = 0
        if st.session_state.slide_index >= len(ppt_slides): st.session_state.slide_index = 0
            
        slide = ppt_slides[st.session_state.slide_index]
        
        with st.container(border=True):
            st.markdown(f"### 问题类型: {slide['title']}")
            c1, c2 = st.columns([1, 1])
            with c1:
                color = "red" if slide['severity'] == "Critical" else "orange" if slide['severity'] == "High" else "blue"
                st.markdown(f"**严重程度:** :{color}[{slide['severity']}]")
                st.markdown(f"**影响范围:** 全站共 **{slide['count']}** 个页面。")
                st.markdown(f"**描述:** {slide['desc']}")
                st.info(f"💡 **建议:** {slide['suggestion']}")
            with c2:
                st.markdown("**🔍 示例:**")
                for ex in slide['examples']: st.markdown(f"- `{ex}`")
                st.image("https://placehold.co/600x300/EEE/31343C?text=Screenshot+Evidence", caption="示例截图")

        c_prev, c_txt, c_next = st.columns([1, 2, 1])
        with c_prev:
            if st.button("⬅️ 上一页"):
                st.session_state.slide_index = max(0, st.session_state.slide_index - 1)
                st.rerun()
        with c_txt:
            st.markdown(f"<div style='text-align: center'>Slide {st.session_state.slide_index + 1} / {len(ppt_slides)}</div>", unsafe_allow_html=True)
        with c_next:
            if st.button("下一页 ➡️"):
                st.session_state.slide_index = min(len(ppt_slides) - 1, st.session_state.slide_index + 1)
                st.rerun()
