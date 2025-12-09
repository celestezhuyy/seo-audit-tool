import streamlit as st
import time
import pandas as pd
import requests
import hashlib
import re
import urllib3
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from io import BytesIO

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 尝试导入 pptx
try:
    from pptx import Presentation
    from pptx.util import Inches, Pt, Cm
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_AUTO_SIZE
    from pptx.enum.shapes import MSO_SHAPE
except ImportError:
    st.error("Missing dependencies! Please add 'python-pptx' to requirements.txt.")
    st.stop()

# --- 1. 页面基础配置 ---
st.set_page_config(
    page_title="NextGen SEO Auditor",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. 排序逻辑配置 ---
# 定义分类的展示顺序 (Storyline)
CATEGORY_ORDER = ["access", "indexability", "technical", "content", "image_ux"]
SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}

# --- 3. 国际化字典 (i18n) ---
TRANSLATIONS = {
    "zh": {
        "sidebar_title": "🔍 AuditAI Pro",
        "sidebar_caption": "深度审计版 v3.6",
        "nav_label": "功能导航",
        "nav_options": ["输入网址", "仪表盘", "数据矩阵", "PPT 生成器"],
        "lang_label": "语言 / Language",
        "clear_data": "清除数据并重置",
        "cache_info": "已缓存 {} 个页面",
        "sitemap_status_title": "Sitemap 状态:",
        "sitemap_found_href": "✅ 发现 Hreflang 配置", 
        "sitemap_no_href": "⚠️ 未发现 Hreflang",     
        
        # PSI 相关
        "psi_settings": "Google PSI API 设置 (可选)",
        "psi_api_key_label": "输入 Google PageSpeed API Key",
        "psi_api_help": "留空则仅进行静态代码检查。填入 Key 可获取首页的真实用户体验数据 (LCP, CLS, INP)。",
        "psi_get_key": "没有 API Key? [点击这里免费申请](https://developers.google.com/speed/docs/insights/v5/get-started)",
        "psi_fetching": "正在调用 Google API 获取首页真实 CWV 数据...",
        "psi_success": "成功获取真实用户数据！",
        "psi_error": "API 调用失败或无 CrUX 数据",
        
        "input_header": "开始深度审计",
        "input_info": "说明: 优化了报告生成逻辑，按照 SEO 审计的标准叙事顺序（索引->技术->内容->体验）排列问题。",
        "input_label": "输入目标网址",
        "input_placeholder": "https://example.com",
        "max_pages_label": "最大爬取页面数",
        "adv_settings": "高级设置 (Advanced Settings)", 
        "manual_robots": "手动 Robots.txt 地址 (可选)", 
        "manual_sitemaps": "手动 Sitemap 地址 (每行一个, 可选)", 
        "start_btn": "开始深度爬取",
        "error_url": "网址格式错误",
        "spinner_crawl": "正在执行深度审计 (Max {} pages)...", 
        "error_no_data": "未能爬取到任何页面。原因: {}", 
        "success_audit": "审计完成！共分析 {} 个页面。",
        
        "dashboard_header": "执行摘要 (Executive Summary)",
        "warn_no_data": "暂无数据。",
        "kpi_health": "网站健康度",
        "kpi_pages": "已分析页面",
        "kpi_issues": "发现问题总数",
        "kpi_critical": "严重问题",
        "chart_issues": "问题类型分布",
        "chart_no_issues": "未发现明显问题。",
        "chart_status": "HTTP 状态码分布",
        "cwv_title": "首页核心 Web 指标 (Core Web Vitals) - 真实数据",
        "cwv_source": "数据来源: Google Chrome User Experience Report (CrUX) - 仅首页",
        
        "matrix_header": "爬取数据明细 (Big Sheet)",
        "download_csv": "下载 CSV 报告",
        
        "ppt_header": "演示文稿预览 (Pitch Deck Mode)",
        "ppt_success_no_issues": "无严重问题。",
        "ppt_download_header": "📥 导出报告",
        "ppt_info": "说明：生成的 PPT 已优化为 16:9 宽屏，问题已按逻辑分类排序。",
        "ppt_btn": "生成并下载美化版 .pptx",
        "ppt_preview_header": "网页版预览",
        "ppt_slide_title": "问题类型:",
        "ppt_category": "分类:",
        "ppt_severity": "严重程度:",
        "ppt_impact": "影响范围:",
        "ppt_impact_desc": "在已爬取样本中发现 **{}** 个页面。",
        "ppt_desc": "描述:",
        "ppt_sugg": "💡 建议:",
        "ppt_examples": "🔍 示例:",
        "ppt_prev": "⬅️ 上一页",
        "ppt_next": "下一页 ➡️",
        
        # Categories
        "cat_access": "1. 可访问性与索引 (Access & Indexing)",
        "cat_indexability": "2. 索引规范性 (Indexability)",
        "cat_technical": "3. 技术与架构 (Technical SEO)",
        "cat_content": "4. 页面内容 (On-Page Content)",
        "cat_image_ux": "5. 体验与资源 (UX & Assets)",

        # PPT Static Text
        "ppt_cover_title": "SEO 深度技术审计报告",
        "ppt_cover_sub": "Generated by AuditAI Pro v3.6",
        "ppt_slide_desc_title": "问题描述 & 影响",
        "ppt_slide_count_title": "样本中受影响页面数: {} 个",
        "ppt_slide_ex_title": "受影响页面示例 & 证据",
        "ppt_slide_sugg_title": "💡 修复建议:",
        "serp_sim_title": "Google 搜索结果模拟:",
    },
    "en": {
        "sidebar_title": "🔍 AuditAI Pro",
        "sidebar_caption": "Deep Audit Edition v3.6",
        "nav_label": "Navigation",
        "nav_options": ["Input URL", "Dashboard", "Data Matrix", "PPT Generator"],
        "lang_label": "Language / 语言",
        "clear_data": "Clear Data & Reset",
        "cache_info": "Cached {} pages",
        "sitemap_status_title": "Sitemap Status:",
        "sitemap_found_href": "✅ Hreflang Found", 
        "sitemap_no_href": "⚠️ No Hreflang",       
        
        # PSI Related
        "psi_settings": "Google PSI API Settings (Optional)",
        "psi_api_key_label": "Enter Google PageSpeed API Key",
        "psi_api_help": "Leave empty for static check only. Enter Key to fetch Real User Metrics (LCP, CLS, INP) for the home page.",
        "psi_get_key": "No API Key? [Get one for free here](https://developers.google.com/speed/docs/insights/v5/get-started)",
        "psi_fetching": "Fetching real CWV data from Google API for Homepage...",
        "psi_success": "Real user data fetched!",
        "psi_error": "API Failed or No CrUX Data",
        
        "input_header": "Start Deep Audit",
        "input_info": "Note: Issues are now sorted logically (Access -> Technical -> Content -> UX).",
        "input_label": "Target URL",
        "input_placeholder": "https://example.com",
        "max_pages_label": "Max Pages to Crawl",
        "adv_settings": "Advanced Settings", 
        "manual_robots": "Manual Robots.txt URL (Optional)", 
        "manual_sitemaps": "Manual Sitemap URLs (One per line, Optional)", 
        "start_btn": "Start Deep Crawl",
        "error_url": "Invalid URL format",
        "spinner_crawl": "Running Deep Audit (Max {} pages)...", 
        "error_no_data": "No pages crawled. Reason: {}", 
        "success_audit": "Audit Complete! Analyzed {} pages.",
        
        "dashboard_header": "Executive Summary",
        "warn_no_data": "No data available.",
        "kpi_health": "Health Score",
        "kpi_pages": "Analyzed Pages",
        "kpi_issues": "Total Issues",
        "kpi_critical": "Critical Issues",
        "chart_issues": "Issue Distribution",
        "chart_no_issues": "No significant issues found.",
        "chart_status": "HTTP Status Codes",
        "cwv_title": "Core Web Vitals - Real User Data (Home Only)",
        "cwv_source": "Source: Google Chrome User Experience Report (CrUX)",
        
        "matrix_header": "Crawled Data Matrix",
        "download_csv": "Download CSV Report",
        
        "ppt_header": "Pitch Deck Preview",
        "ppt_success_no_issues": "No critical issues found.",
        "ppt_download_header": "📥 Export Report",
        "ppt_info": "Note: PPT optimized for 16:9 with logical issue ordering.",
        "ppt_btn": "Generate & Download .pptx",
        "ppt_preview_header": "Web Preview",
        "ppt_slide_title": "Issue Type:",
        "ppt_category": "Category:",
        "ppt_severity": "Severity:",
        "ppt_impact": "Impact:",
        "ppt_impact_desc": "Affects **{}** pages in crawled sample.",
        "ppt_desc": "Description:",
        "ppt_sugg": "💡 Suggestion:",
        "ppt_examples": "🔍 Examples:",
        "ppt_prev": "⬅️ Previous",
        "ppt_next": "Next ➡️",
        
        # Categories
        "cat_access": "1. Access & Indexing",
        "cat_indexability": "2. Indexability",
        "cat_technical": "3. Technical SEO",
        "cat_content": "4. On-Page Content",
        "cat_image_ux": "5. UX & Assets",
        
        "ppt_cover_title": "SEO Technical Audit",
        "ppt_cover_sub": "Generated by AuditAI Pro v3.6",
        "ppt_slide_desc_title": "Description & Impact",
        "ppt_slide_count_title": "Affected Pages (in sample): {}",
        "ppt_slide_ex_title": "Example URLs & Evidence",
        "ppt_slide_sugg_title": "💡 Recommendation:",
        "serp_sim_title": "Google SERP Simulation:",
    }
}

# --- 4. 爬虫核心引擎 (支持多语言) ---

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def get_content_hash(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def get_browser_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
    }

# --- Google PSI API Integration ---
def fetch_psi_data(url, api_key):
    """Call Google PageSpeed Insights API"""
    if not api_key: return None
    
    endpoint = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&key={api_key}&strategy=mobile"
    try:
        response = requests.get(endpoint, timeout=30)
        if response.status_code == 200:
            data = response.json()
            crux = data.get('loadingExperience', {}).get('metrics', {})
            if not crux: return {"error": "No CrUX data available for this URL."}
            
            return {
                "LCP": crux.get('LARGEST_CONTENTFUL_PAINT_MS', {}).get('percentile', 0) / 1000,
                "CLS": crux.get('CUMULATIVE_LAYOUT_SHIFT_SCORE', {}).get('percentile', 0) / 100,
                "INP": crux.get('INTERACTION_TO_NEXT_PAINT', {}).get('percentile', 0),
                "FCP": crux.get('FIRST_CONTENTFUL_PAINT_MS', {}).get('percentile', 0) / 1000,
            }
        else:
            return {"error": f"API Error: {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def check_site_level_assets(start_url, lang="zh", manual_robots=None, manual_sitemaps=None):
    issues = []
    sitemap_has_hreflang = False
    
    parsed_url = urlparse(start_url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    headers = get_browser_headers()
    
    t = TRANSLATIONS[lang]

    # --- 1. Robots.txt (Category: Access) ---
    robots_url = manual_robots if manual_robots else urljoin(base_url, "/robots.txt")
    try:
        r = requests.get(robots_url, headers=headers, timeout=10, allow_redirects=True, stream=True, verify=False)
        if r.status_code != 200:
            issues.append({"category": "access", "severity": "Medium", "title": t["zh"]["no_robots"] if lang=="zh" else t["en"]["no_robots"], "desc": f"Status: {r.status_code}", "suggestion": "Ensure robots.txt exists.", "url": robots_url})
        else:
            content = r.text.lower()
            if "disallow: /" in content and "allow:" not in content:
                 issues.append({"category": "access", "severity": "Critical", "title": t["zh"]["robots_bad_rule"] if lang=="zh" else t["en"]["robots_bad_rule"], "desc": "Found 'Disallow: /' which blocks ALL crawling.", "suggestion": "Remove global disallow rule.", "url": robots_url})
            if "sitemap:" not in content:
                 issues.append({"category": "access", "severity": "Low", "title": t["zh"]["robots_no_sitemap"] if lang=="zh" else t["en"]["robots_no_sitemap"], "desc": "Sitemap location not specified.", "suggestion": "Add 'Sitemap: [URL]' directive.", "url": robots_url})
        r.close()
    except: 
        issues.append({"category": "access", "severity": "Medium", "title": t["zh"]["no_robots"] if lang=="zh" else t["en"]["no_robots"], "desc": "Connection failed.", "suggestion": "Check server config.", "url": robots_url})

    # --- 2. Sitemap (Category: Access) ---
    sitemap_urls_to_check = manual_sitemaps if manual_sitemaps else [urljoin(base_url, "/sitemap.xml")]
    any_sitemap_valid = False
    
    for sitemap_url in sitemap_urls_to_check:
        sitemap_url = sitemap_url.strip()
        if not sitemap_url: continue
        try:
            r = requests.get(sitemap_url, headers=headers, timeout=15, allow_redirects=True, verify=False)
            if r.status_code == 200:
                try:
                    root = ET.fromstring(r.content)
                    any_sitemap_valid = True
                    if 'xhtml' in r.text or 'hreflang' in r.text:
                        sitemap_has_hreflang = True
                except ET.ParseError:
                    if not sitemap_url.endswith('.gz'): 
                        issues.append({"category": "access", "severity": "Medium", "title": t["zh"]["sitemap_invalid"] if lang=="zh" else t["en"]["sitemap_invalid"], "desc": "XML parsing failed.", "suggestion": "Check XML syntax.", "url": sitemap_url})
            else:
                if manual_sitemaps:
                    issues.append({"category": "access", "severity": "Low", "title": t["zh"]["no_sitemap"] if lang=="zh" else t["en"]["no_sitemap"], "desc": f"Status: {r.status_code}", "suggestion": "Check URL.", "url": sitemap_url})
        except:
            if manual_sitemaps: issues.append({"category": "access", "severity": "Low", "title": t["zh"]["no_sitemap"] if lang=="zh" else t["en"]["no_sitemap"], "desc": "Connection failed.", "suggestion": "Check URL.", "url": sitemap_url})

    if not any_sitemap_valid and not manual_sitemaps:
         issues.append({"category": "access", "severity": "Low", "title": t["zh"]["no_sitemap"] if lang=="zh" else t["en"]["no_sitemap"], "desc": "Default sitemap not found.", "suggestion": "Ensure sitemap.xml exists.", "url": sitemap_urls_to_check[0]})

    return issues, sitemap_has_hreflang

def analyze_page(url, html_content, status_code, lang="zh", sitemap_has_hreflang=False):
    soup = BeautifulSoup(html_content, 'html.parser')
    issues = []
    
    # 语言包 (Simplified access)
    t = TRANSLATIONS[lang][lang]
    
    for script in soup(["script", "style"]): script.extract()
    text_content = soup.get_text().strip()
    content_hash = get_content_hash(text_content)

    # --- Technical ---
    # Hreflang
    hreflangs = soup.find_all('link', hreflang=True)
    if hreflangs:
        has_x_default = False
        invalid_codes = []
        code_pattern = re.compile(r'^[a-z]{2}(-[a-zA-Z]{2})?$|x-default', re.IGNORECASE)
        for link in hreflangs:
            code = link.get('hreflang', '').strip()
            if code.lower() == 'x-default': has_x_default = True
            if not code_pattern.match(code): invalid_codes.append(code)
        
        if invalid_codes:
            issues.append({"category": "technical", "severity": "High", "title": t["hreflang_invalid"], "desc": f"{t['hreflang_invalid_desc']} Found: {', '.join(invalid_codes[:3])}", "suggestion": "Use ISO 639-1 codes.", "url": url})
        if not has_x_default:
            issues.append({"category": "technical", "severity": "Low", "title": t["hreflang_no_default"], "desc": t["hreflang_no_default_desc"], "suggestion": "Add hreflang='x-default'.", "url": url})
    elif not sitemap_has_hreflang:
        issues.append({"category": "technical", "severity": "Low", "title": t["missing_hreflang"], "desc": t["missing_hreflang_desc"], "suggestion": t["missing_hreflang_sugg"], "url": url})

    # Viewport
    if not soup.find('meta', attrs={'name': 'viewport'}):
        issues.append({"category": "technical", "severity": "Critical", "title": t["missing_viewport"], "desc": t["missing_viewport_desc"], "suggestion": t["missing_viewport_sugg"], "url": url})

    # Canonical
    canonical_tag = soup.find('link', attrs={'rel': 'canonical'})
    canonical_url = canonical_tag['href'] if canonical_tag else None
    if not canonical_url:
        issues.append({"category": "indexability", "severity": "Medium", "title": t["missing_canonical"], "desc": t["missing_canonical_desc"], "suggestion": t["missing_canonical_sugg"], "url": url})

    # Schema
    if not soup.find('script', type='application/ld+json'):
         issues.append({"category": "technical", "severity": "Medium", "title": t["missing_jsonld"], "desc": t["missing_jsonld_desc"], "suggestion": t["missing_jsonld_sugg"], "url": url})

    # URL
    parsed_url = urlparse(url)
    path = parsed_url.path
    if '_' in path:
         issues.append({"category": "technical", "severity": "Low", "title": t["url_underscore"], "desc": t["url_underscore_desc"], "suggestion": t["url_underscore_sugg"], "url": url})
    if any(c.isupper() for c in path):
         issues.append({"category": "technical", "severity": "Medium", "title": t["url_uppercase"], "desc": t["url_uppercase_desc"], "suggestion": t["url_uppercase_sugg"], "url": url})

    # JS Links
    js_links = soup.find_all('a', href=lambda x: x and x.lower().startswith('javascript:'))
    if js_links:
        issues.append({"category": "technical", "severity": "High", "title": t["js_links"], "desc": t["js_links_desc"], "suggestion": t["js_links_sugg"], "url": url, "meta": f"Count: {len(js_links)}"})

    # --- UX & Assets ---
    images = soup.find_all('img')
    missing_alt = 0
    bad_alt_count = 0
    cls_risk_count = 0
    bad_keywords = ["image", "photo", "picture", "img", "untitled", ".jpg", ".png"]
    
    for img in images:
        alt = img.get('alt', '').strip()
        if not alt: missing_alt += 1
        else:
            if len(alt) < 3 or any(bk in alt.lower() for bk in bad_keywords): bad_alt_count += 1
        if not img.get('width') or not img.get('height'): cls_risk_count += 1

    if missing_alt > 0:
        issues.append({"category": "image_ux", "severity": "Medium", "title": t["missing_alt"], "desc": f"{missing_alt} {t['missing_alt_desc']}", "suggestion": t["missing_alt_sugg"], "url": url})
    if bad_alt_count > 0:
        issues.append({"category": "image_ux", "severity": "Low", "title": t["alt_bad_quality"], "desc": t["alt_bad_quality_desc"], "suggestion": "Avoid generic keywords.", "url": url, "evidence": f"{bad_alt_count} poor alts"})
    if cls_risk_count > 0:
        issues.append({"category": "image_ux", "severity": "Medium", "title": t["cls_risk"], "desc": t["cls_risk_desc"], "suggestion": "Always specify width/height.", "url": url, "evidence": f"{cls_risk_count} images without dims"})

    links = soup.find_all('a', href=True)
    bad_anchors = ["click here", "read more", "learn more", "more", "here", "link", "点击这里", "更多", "详情"]
    found_bad = []
    for link in links:
        at = link.get_text().strip().lower()
        if at in bad_anchors: found_bad.append(at)
    if found_bad:
        issues.append({"category": "image_ux", "severity": "Low", "title": t["anchor_bad_quality"], "desc": f"{t['anchor_bad_quality_desc']} ({len(found_bad)})", "suggestion": "Use descriptive keywords.", "url": url})

    # --- Content ---
    title_tag = soup.title
    title = title_tag.string.strip() if title_tag and title_tag.string else None
    if not title:
        issues.append({"category": "content", "severity": "High", "title": t["missing_title"], "desc": t["missing_title_desc"], "suggestion": t["missing_title_sugg"], "url": url})
    elif len(title) < 10:
         issues.append({"category": "content", "severity": "Medium", "title": t["short_title"], "desc": t["short_title_desc"], "suggestion": t["short_title_sugg"], "url": url, "evidence": title})
    elif len(title) > 60:
         issues.append({"category": "content", "severity": "Low", "title": t["long_title"], "desc": t["long_title_desc"], "suggestion": t["long_title_sugg"], "url": url, "evidence": title})

    meta_desc = soup.find('meta', attrs={'name': 'description'})
    desc_content = meta_desc['content'].strip() if meta_desc and meta_desc.get('content') else None
    if not desc_content:
        issues.append({"category": "content", "severity": "High", "title": t["missing_desc"], "desc": t["missing_desc_desc"], "suggestion": t["missing_desc_sugg"], "url": url})
    elif len(desc_content) < 50:
        issues.append({"category": "content", "severity": "Low", "title": t["short_desc"], "desc": t["short_desc_desc"], "suggestion": t["short_desc_sugg"], "url": url, "evidence": desc_content})

    h1 = soup.find('h1')
    if not h1: issues.append({"category": "content", "severity": "High", "title": t["missing_h1"], "desc": t["missing_h1_desc"], "suggestion": t["missing_h1_sugg"], "url": url})

    if status_code == 200:
        error_kws = ["page not found", "404 error", "页面未找到"]
        is_s404 = False
        if title and any(k in title.lower() for k in error_kws): is_s404 = True
        elif soup.find('h1') and any(k in soup.find('h1').get_text().lower() for k in error_kws): is_s404 = True
        if is_s404:
            issues.append({"category": "access", "severity": "Critical", "title": t["soft_404"], "desc": t["soft_404_desc"], "suggestion": t["soft_404_sugg"], "url": url})

    return {
        "URL": url, "Status": status_code, "Title": title or "No Title",
        "H1": h1.get_text().strip() if h1 else "No H1", "Links_Count": len(soup.find_all('a')),
        "Issues_Count": len(issues), "Content_Hash": content_hash, "Canonical": canonical_url
    }, issues, []

def crawl_website(start_url, max_pages=100, lang="zh", manual_robots=None, manual_sitemaps=None, psi_key=None):
    visited = set()
    seen_hashes = {} 
    seen_urls = set()
    queue = [start_url]
    seen_urls.add(start_url)
    results_data = []
    all_issues = []
    first_error = None
    target_domain = None
    
    # 辅助函数: 清理 URL 参数
    def clean_url(u): return u.split('?')[0].split('#')[0]

    # UI Text
    t = TRANSLATIONS[lang][lang]
    t_dup_title = t["duplicate"]
    t_dup_desc = t["duplicate_desc"]
    t_dup_sugg = t["duplicate_sugg"]
    
    t_3xx_title = "Internal Redirect (3xx)" if lang == "en" else "内部链接重定向 (3xx)"
    t_3xx_desc = "Internal link redirects." if lang == "en" else "内部链接发生跳转，浪费预算。"
    t_4xx_title = "Broken Link (4xx)" if lang == "en" else "死链 (4xx)"
    t_5xx_title = "Server Error (5xx)" if lang == "en" else "服务器错误 (5xx)"

    progress_bar = st.progress(0, text="Initializing...")
    sitemap_has_hreflang = False
    
    try:
        site_issues, sitemap_has_hreflang = check_site_level_assets(
            start_url, lang=lang, manual_robots=manual_robots, manual_sitemaps=manual_sitemaps
        )
        all_issues.extend(site_issues)
        st.session_state['sitemap_hreflang_found'] = sitemap_has_hreflang
    except Exception as e:
        pass

    if psi_key:
        with st.spinner(TRANSLATIONS[lang]["psi_fetching"]):
            cwv_data = fetch_psi_data(start_url, psi_key)
            if cwv_data and "error" not in cwv_data: st.session_state['cwv_data'] = cwv_data
            else: st.session_state['cwv_data'] = None

    pages_crawled = 0
    headers = get_browser_headers()
    
    while queue and pages_crawled < max_pages:
        url = queue.pop(0)
        visited.add(url)
        pages_crawled += 1
        progress = int((pages_crawled / max_pages) * 100)
        progress_bar.progress(progress, text=f"Crawling ({pages_crawled}/{max_pages}): {url}")
        time.sleep(0.1)
        
        try:
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True, verify=False)
            current_url = response.url 
            if target_domain is None: target_domain = urlparse(current_url).netloc
            final_status = response.status_code

            # 1. 3xx Check (History)
            if response.history:
                all_issues.append({"category": "access", "severity": "Medium", "title": t_3xx_title, "desc": f"{t_3xx_desc} -> {current_url}", "suggestion": "Update link.", "url": url})

            # 2. 4xx/5xx Check
            if final_status >= 400:
                is_5xx = final_status >= 500
                all_issues.append({"category": "access", "severity": "Critical" if is_5xx else "High", "title": t_5xx_title if is_5xx else t_4xx_title, "desc": f"Status: {final_status}", "suggestion": "Fix link.", "url": url})

            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' in content_type:
                page_data, page_issues, _ = analyze_page(current_url, response.content, final_status, lang=lang, sitemap_has_hreflang=sitemap_has_hreflang)
                
                # --- Advanced Deduplication ---
                if final_status == 200:
                    current_hash = page_data['Content_Hash']
                    current_canonical = page_data['Canonical']
                    current_clean = clean_url(current_url)
                    
                    if current_hash in seen_hashes:
                        original_url = seen_hashes[current_hash]
                        original_clean = clean_url(original_url)
                        
                        # A. 升级原件逻辑：如果当前 URL 更短且无参数，即使后发现，也视为原件
                        if len(current_url) < len(original_url) and '?' not in current_url and '?' in original_url:
                            seen_hashes[current_hash] = current_url
                        # B. 如果只是参数变化 (main vs main?sort=1)
                        elif current_clean == original_clean:
                            # 只要 Canonical 指向了 Base URL，就算 Pass
                            if not (current_canonical and current_canonical == current_clean):
                                # 严格模式：必须有 canonical
                                pass 
                        else:
                            # C. 真正的重复内容
                            is_handled = current_canonical and current_canonical != current_url
                            if not is_handled:
                                page_issues.append({"category": "indexability", "severity": "High", "title": t_dup_title, "desc": f"{t_dup_desc} (Original: {original_url})", "suggestion": t_dup_sugg, "url": current_url, "meta": f"Duplicate of: {original_url}"})
                    else:
                        seen_hashes[current_hash] = current_url

                results_data.append(page_data)
                all_issues.extend(page_issues)
                
                soup = BeautifulSoup(response.content, 'html.parser')
                for a in soup.find_all('a', href=True):
                    link = urljoin(current_url, a['href'])
                    if urlparse(link).netloc == target_domain and link not in seen_urls:
                        if not any(link.lower().endswith(ext) for ext in ['.jpg', '.png', '.pdf', '.zip']):
                            seen_urls.add(link)
                            queue.append(link)
            else:
                if pages_crawled == 1: first_error = f"Content type: {content_type}"
        except Exception as e:
            if pages_crawled == 1: first_error = str(e)
            pass
    
    progress_bar.progress(100, text="Done!")
    time.sleep(0.5)
    progress_bar.empty()
    if not results_data and first_error: return None, None, first_error
    return results_data, all_issues, None

def create_styled_pptx(slides_data, lang="zh"):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    txt = TRANSLATIONS[lang] 
    
    def set_font(font_obj, size, bold=False, color=None):
        font_obj.size = Pt(size)
        font_obj.name = 'Microsoft YaHei' if lang == "zh" else 'Arial'
        font_obj.bold = bold
        if color: font_obj.color.rgb = color

    def draw_serp_preview(slide, issue_title, evidence, url):
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(7), Inches(2), Inches(5.8), Inches(2.5))
        box.fill.solid()
        box.fill.fore_color.rgb = RGBColor(255, 255, 255)
        box.line.color.rgb = RGBColor(220, 220, 220)
        tf = box.text_frame
        tf.margin_left = Inches(0.2)
        tf.margin_top = Inches(0.2)
        
        p = tf.add_paragraph()
        domain = urlparse(url).netloc
        p.text = f"{domain} › ..."
        set_font(p.font, 12, False, RGBColor(32, 33, 36))
        
        p = tf.add_paragraph()
        p.space_before = Pt(5)
        display_title = evidence if evidence else "Untitled Page"
        if len(display_title) > 60 and ("Long" in issue_title or "过长" in issue_title):
            display_title = display_title[:55] + " ..."
        p.text = display_title
        set_font(p.font, 18, False, RGBColor(26, 13, 171)) 
        p = tf.add_paragraph()
        p.space_before = Pt(3)
        p.text = "Please provide a meta description..."
        set_font(p.font, 14, False, RGBColor(77, 81, 86))
        label = slide.shapes.add_textbox(Inches(7), Inches(1.6), Inches(3), Inches(0.3))
        p = label.text_frame.add_paragraph()
        p.text = txt["serp_sim_title"]
        set_font(p.font, 12, True, RGBColor(100, 100, 100))

    # Cover
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.shapes.add_shape(1, 0, 0, Inches(13.333), Inches(7.5))
    bg.fill.solid()
    bg.fill.fore_color.rgb = RGBColor(18, 52, 86)
    
    title = slide.shapes.add_textbox(Inches(1), Inches(2.5), Inches(11), Inches(2))
    p = title.text_frame.add_paragraph()
    p.text = txt["ppt_cover_title"]
    p.alignment = PP_ALIGN.CENTER
    set_font(p.font, 54, True, RGBColor(255, 255, 255))
    
    sub = slide.shapes.add_textbox(Inches(1), Inches(4), Inches(11), Inches(1))
    p = sub.text_frame.add_paragraph()
    p.text = txt["ppt_cover_sub"]
    p.alignment = PP_ALIGN.CENTER
    set_font(p.font, 24, False, RGBColor(200, 200, 200))

    # Slides
    for issue in slides_data:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        
        # Header
        h_shape = slide.shapes.add_shape(1, 0, 0, Inches(13.333), Inches(1.2))
        h_shape.fill.solid()
        h_shape.fill.fore_color.rgb = RGBColor(240, 242, 246)
        
        h_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(10), Inches(0.8))
        p = h_box.text_frame.add_paragraph()
        p.text = issue['title']
        set_font(p.font, 32, True, RGBColor(50, 50, 50))
        
        # Severity
        sev_color = RGBColor(220, 53, 69) if issue['severity'] == "Critical" else RGBColor(253, 126, 20)
        sev_box = slide.shapes.add_textbox(Inches(11), Inches(0.35), Inches(2), Inches(0.5))
        p = sev_box.text_frame.add_paragraph()
        p.text = f"{issue['severity']}"
        p.alignment = PP_ALIGN.CENTER
        set_font(p.font, 18, True, sev_color)
        
        # Category Label (New)
        cat_key = f"cat_{issue['category']}"
        cat_label = txt.get(cat_key, issue['category'].upper())
        cat_box = slide.shapes.add_textbox(Inches(0.5), Inches(1.3), Inches(4), Inches(0.4))
        p = cat_box.text_frame.add_paragraph()
        p.text = cat_label
        set_font(p.font, 14, True, RGBColor(0, 102, 204))

        # Desc
        d_title = slide.shapes.add_textbox(Inches(0.5), Inches(1.8), Inches(6), Inches(0.5))
        p = d_title.text_frame.add_paragraph()
        p.text = txt["ppt_slide_desc_title"]
        set_font(p.font, 18, True, RGBColor(30, 30, 30))
        
        d_box = slide.shapes.add_textbox(Inches(0.5), Inches(2.3), Inches(6), Inches(2.5))
        tf = d_box.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
        p = tf.add_paragraph()
        p.text = issue['desc']
        set_font(p.font, 14, False, RGBColor(80, 80, 80))
        
        c_box = slide.shapes.add_textbox(Inches(0.5), Inches(3.8), Inches(6), Inches(0.5))
        p = c_box.text_frame.add_paragraph()
        p.text = txt["ppt_slide_count_title"].format(issue['count'])
        set_font(p.font, 14, True, RGBColor(100, 100, 100))

        is_serp = any(k in issue['title'] for k in ["Title", "标题", "Meta", "元描述"])
        ev = issue.get('example_evidence', '')
        ex_url = issue['examples'][0] if issue['examples'] else "example.com"
        
        if is_serp:
            draw_serp_preview(slide, issue['title'], ev, ex_url)
        else:
            e_title = slide.shapes.add_textbox(Inches(7), Inches(1.8), Inches(5.8), Inches(0.5))
            p = e_title.text_frame.add_paragraph()
            p.text = txt["ppt_slide_ex_title"]
            set_font(p.font, 18, True, RGBColor(30, 30, 30))
            
            e_box = slide.shapes.add_textbox(Inches(7), Inches(2.3), Inches(5.8), Inches(2.5))
            tf = e_box.text_frame
            tf.word_wrap = True
            tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
            for url in issue['examples'][:5]:
                p = tf.add_paragraph()
                p.text = f"• {url}"
                set_font(p.font, 12, False, RGBColor(0, 102, 204))
                p.space_after = Pt(6)

        s_bg = slide.shapes.add_shape(1, Inches(0.5), Inches(5.8), Inches(12.333), Inches(1.5))
        s_bg.fill.solid()
        s_bg.fill.fore_color.rgb = RGBColor(230, 244, 234)
        s_bg.line.color.rgb = RGBColor(40, 167, 69)
        
        s_box = slide.shapes.add_textbox(Inches(0.7), Inches(5.9), Inches(11.9), Inches(1.3))
        tf = s_box.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
        p = tf.add_paragraph()
        p.text = txt["ppt_slide_sugg_title"]
        set_font(p.font, 16, True, RGBColor(21, 87, 36))
        p = tf.add_paragraph()
        p.text = issue['suggestion']
        set_font(p.font, 14, False, RGBColor(21, 87, 36))
        p.space_before = Pt(5)

    out = BytesIO()
    prs.save(out)
    out.seek(0)
    return out

# --- 4. Init Session ---
if 'audit_data' not in st.session_state: st.session_state['audit_data'] = None
if 'audit_issues' not in st.session_state: st.session_state['audit_issues'] = []
if 'language' not in st.session_state: st.session_state['language'] = "zh" 
if 'sitemap_hreflang_found' not in st.session_state: st.session_state['sitemap_hreflang_found'] = False
if 'cwv_data' not in st.session_state: st.session_state['cwv_data'] = None

# --- 5. Sidebar ---
lang = st.session_state['language']
ui = TRANSLATIONS[lang]

with st.sidebar:
    st.title(ui["sidebar_title"])
    st.caption(ui["sidebar_caption"])
    
    st.divider()
    selected_lang = st.radio(ui["lang_label"], ["中文", "English"], index=0 if lang=="zh" else 1)
    new_lang = "zh" if selected_lang == "中文" else "en"
    if new_lang != lang:
        st.session_state['language'] = new_lang
        st.rerun()
    
    st.divider()
    menu_options = ui["nav_options"]
    menu_map = {ui["nav_options"][i]: ["input", "dashboard", "matrix", "ppt"][i] for i in range(4)}
    selected_menu = st.radio(ui["nav_label"], menu_options)
    menu_key = menu_map[selected_menu]
    
    st.divider()
    if st.session_state['audit_data'] is not None:
        st.success(ui["cache_info"].format(len(st.session_state['audit_data'])))
        st.markdown(f"**{ui['sitemap_status_title']}**")
        if st.session_state['sitemap_hreflang_found']: st.caption(ui["sitemap_found_href"])
        else: st.caption(ui["sitemap_no_href"])
        if st.button(ui["clear_data"]):
            st.session_state['audit_data'] = None
            st.session_state['audit_issues'] = []
            st.session_state['sitemap_hreflang_found'] = False
            st.session_state['cwv_data'] = None
            st.rerun()

# --- 6. Main Logic ---
if menu_key == "input":
    st.header(ui["input_header"])
    st.info(ui["input_info"])
    
    col1, col2 = st.columns([3, 1])
    with col1:
        url_input = st.text_input(ui["input_label"], placeholder=ui["input_placeholder"])
    with col2:
        max_pages = st.number_input(ui.get("max_pages_label", "Max Pages"), min_value=1, max_value=1000, value=100)
    
    with st.expander(ui.get("adv_settings", "Advanced")):
        manual_robots = st.text_input(ui.get("manual_robots", "Manual Robots.txt"), placeholder="https://example.com/robots.txt")
        manual_sitemaps_text = st.text_area(ui.get("manual_sitemaps", "Manual Sitemaps"), placeholder="https://example.com/sitemap.xml")
        manual_sitemaps = [s.strip() for s in manual_sitemaps_text.split('\n') if s.strip()]
    
    with st.expander(ui.get("psi_settings", "Google PSI")):
        psi_key = st.text_input(ui.get("psi_api_key_label", "API Key"), type="password", help=ui.get("psi_api_help", ""))
        st.caption(ui["psi_get_key"])

    start_btn = st.button(ui["start_btn"], type="primary", use_container_width=True)
    
    if start_btn and url_input:
        if not is_valid_url(url_input):
            st.error(ui["error_url"])
        else:
            with st.spinner(ui["spinner_crawl"].format(max_pages)):
                data, issues, error_msg = crawl_website(url_input, max_pages, lang, manual_robots, manual_sitemaps, psi_key)
                if not data:
                    st.error(ui["error_no_data"].format(error_msg or "Unknown Error"))
                else:
                    st.session_state['audit_data'] = data
                    st.session_state['audit_issues'] = issues
                    st.success(ui["success_audit"].format(len(data)))
                    st.balloons()

elif menu_key == "dashboard":
    st.header(ui["dashboard_header"])
    if st.session_state['audit_data'] is None:
        st.warning(ui["warn_no_data"])
    else:
        if st.session_state.get('cwv_data'):
            cwv = st.session_state['cwv_data']
            st.subheader(ui["cwv_title"])
            st.caption(ui["cwv_source"])
            c1, c2, c3, c4 = st.columns(4)
            def metric_color(val, good, poor):
                if val <= good: return "normal"
                if val >= poor: return "inverse"
                return "off"
            c1.metric("LCP (Loading)", f"{cwv.get('LCP',0):.2f}s", delta_color=metric_color(cwv.get('LCP',0), 2.5, 4.0))
            c2.metric("CLS (Visual)", f"{cwv.get('CLS',0):.3f}", delta_color=metric_color(cwv.get('CLS',0), 0.1, 0.25))
            c3.metric("INP (Interact)", f"{cwv.get('INP',0)}ms", delta_color=metric_color(cwv.get('INP',0), 200, 500))
            c4.metric("FCP", f"{cwv.get('FCP',0):.2f}s")
            st.divider()

        df = pd.DataFrame(st.session_state['audit_data'])
        issues = st.session_state['audit_issues']
        total = len(issues)
        score = max(0, 100 - int(total * 0.5))
        critical = len([i for i in issues if i['severity'] == 'Critical'])
        
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(ui["kpi_health"], f"{score}/100")
        k2.metric(ui["kpi_pages"], str(len(df)))
        k3.metric(ui["kpi_issues"], str(total), delta_color="inverse")
        k4.metric(ui["kpi_critical"], str(critical), delta_color="inverse")
        
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.subheader(ui["chart_issues"])
            if issues: st.bar_chart(pd.DataFrame(issues)['title'].value_counts())
            else: st.info(ui["chart_no_issues"])
        with c2:
            st.subheader(ui["chart_status"])
            if not df.empty: st.bar_chart(df['Status'].value_counts())

elif menu_key == "matrix":
    st.header(ui["matrix_header"])
    if st.session_state['audit_data'] is None:
        st.warning(ui["warn_no_data"])
    else:
        df = pd.DataFrame(st.session_state['audit_data'])
        st.dataframe(df, use_container_width=True, hide_index=True)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(ui["download_csv"], csv, "audit_report.csv", "text/csv")

elif menu_key == "ppt":
    st.header(ui["ppt_header"])
    if st.session_state['audit_data'] is None:
        st.warning(ui["warn_no_data"])
    elif not st.session_state['audit_issues']:
        st.success(ui["ppt_success_no_issues"])
    else:
        raw_issues = st.session_state['audit_issues']
        grouped = {}
        for i in raw_issues:
            t = i['title']
            if t not in grouped:
                grouped[t] = {
                    "title": t, "severity": i['severity'], "desc": i['desc'], 
                    "suggestion": i['suggestion'], "count": 0, "examples": [],
                    "example_evidence": i.get("evidence", ""),
                    "category": i.get("category", "content") # Default to content
                }
            grouped[t]['count'] += 1
            if len(grouped[t]['examples']) < 5: grouped[t]['examples'].append(i['url'])
        
        # Sort by Category -> Severity -> Count
        sov_order = SEVERITY_ORDER
        cat_order = {k: v for v, k in enumerate(CATEGORY_ORDER)}
        
        slides = sorted(list(grouped.values()), key=lambda x: (
            cat_order.get(x['category'], 99), 
            sov_order.get(x['severity'], 3), 
            -x['count']
        ))

        st.write(f"### {ui['ppt_download_header']}")
        st.info(ui["ppt_info"])
        if st.button(ui["ppt_btn"]):
            with st.spinner("Generating..."):
                pptx = create_styled_pptx(slides, lang=lang)
                fname = f"seo_audit_report_{lang}.pptx"
                st.download_button(ui["ppt_btn"], pptx, fname, "application/vnd.openxmlformats-officedocument.presentationml.presentation")

        st.divider()
        st.subheader(ui["ppt_preview_header"])
        
        if 'slide_index' not in st.session_state: st.session_state.slide_index = 0
        if st.session_state.slide_index >= len(slides): st.session_state.slide_index = 0
        
        s = slides[st.session_state.slide_index]
        with st.container(border=True):
            # Display Category Label
            cat_key = f"cat_{s['category']}"
            cat_label = ui.get(cat_key, s['category'].upper())
            st.caption(f"📂 {cat_label}")
            
            st.markdown(f"### {ui['ppt_slide_title']} {s['title']}")
            c1, c2 = st.columns([1, 1])
            with c1:
                color = "red" if s['severity'] == "Critical" else "orange" if s['severity'] == "High" else "blue"
                st.markdown(f"**{ui['ppt_severity']}** :{color}[{s['severity']}]")
                st.markdown(f"**{ui['ppt_impact']}** {ui['ppt_impact_desc'].format(s['count'])}")
                st.markdown(f"**{ui['ppt_desc']}** {s['desc']}")
                st.info(f"{ui['ppt_sugg']} {s['suggestion']}")
            with c2:
                is_serp = any(k in s['title'] for k in ["Title", "标题", "Meta", "元描述"])
                if is_serp:
                    st.markdown(f"**{ui.get('serp_sim_title', 'SERP Preview')}**")
                    ev = s.get('example_evidence', '')
                    ex_url = s['examples'][0] if s['examples'] else "example.com"
                    display_title = ev if ev else "Untitled Page"
                    if len(display_title) > 60: display_title = display_title[:55] + " ..."
                    st.markdown(f"""
                    <div style="font-family: Arial, sans-serif; border: 1px solid #dfe1e5; border-radius: 8px; padding: 15px; background: white; box-shadow: 0 1px 6px rgba(32,33,36,0.28);">
                        <div style="font-size: 14px; color: #202124;">{urlparse(ex_url).netloc} <span style="color: #5f6368">› ...</span></div>
                        <div style="font-size: 20px; color: #1a0dab; margin-top: 5px;">{display_title}</div>
                        <div style="font-size: 14px; color: #4d5156; margin-top: 3px;">
                            Please provide a meta description...
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"**{ui['ppt_examples']}**")
                    for ex in s['examples']: st.markdown(f"- `{ex}`")

        cp, ct, cn = st.columns([1, 2, 1])
        with cp:
            if st.button(ui["ppt_prev"]):
                st.session_state.slide_index = max(0, st.session_state.slide_index - 1)
                st.rerun()
        with ct:
            st.markdown(f"<div style='text-align: center'>Slide {st.session_state.slide_index + 1} / {len(slides)}</div>", unsafe_allow_html=True)
        with cn:
            if st.button(ui["ppt_next"]):
                st.session_state.slide_index = min(len(slides) - 1, st.session_state.slide_index + 1)
                st.rerun()
