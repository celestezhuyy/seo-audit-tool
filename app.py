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
CATEGORY_ORDER = ["access", "indexability", "technical", "content", "image_ux"]
SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}

# --- 3. 国际化字典 (i18n) ---
TRANSLATIONS = {
    "zh": {
        "sidebar_title": "🔍 AuditAI Pro",
        "sidebar_caption": "深度审计版 v3.8.2",
        "nav_label": "功能导航",
        "nav_options": ["输入网址", "仪表盘", "数据矩阵", "PPT 生成器"],
        "lang_label": "语言 / Language",
        "clear_data": "清除数据并重置",
        "cache_info": "已缓存 {} 个页面",
        "sitemap_status_title": "Sitemap 状态:",
        "sitemap_found_href": "✅ 发现 Hreflang 配置", 
        "sitemap_no_href": "⚠️ 未发现 Hreflang",     
        "sitemap_missing": "❌ 未找到 Sitemap",

        # PSI 相关
        "psi_settings": "Google PSI API 设置 (可选)",
        "psi_api_key_label": "输入 Google PageSpeed API Key",
        "psi_api_help": "留空则仅进行静态代码检查。填入 Key 可获取首页的真实用户体验数据 (LCP, CLS, INP)。",
        "psi_get_key": "没有 API Key? [点击这里免费申请](https://developers.google.com/speed/docs/insights/v5/get-started)",
        "psi_fetching": "正在调用 Google API 获取首页真实 CWV 数据...",
        "psi_success": "成功获取真实用户数据！",
        "psi_error": "API 调用失败或无 CrUX 数据",
        
        "input_header": "开始深度审计",
        "input_info": "说明: v3.8 包含富媒体结果模拟、商业影响深度分析及智能分类逻辑。",
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
        "ppt_info": "说明：生成的 PPT 已优化为 16:9 宽屏，包含 SERP/Rich Snippet 预览。",
        "ppt_btn": "生成并下载美化版 .pptx",
        "ppt_preview_header": "网页版预览",
        "ppt_slide_title": "问题类型:",
        "ppt_category": "分类:",
        "ppt_severity": "严重程度:",
        "ppt_impact": "影响范围:",
        "ppt_impact_desc": "在已爬取样本中发现 **{}** 个页面。",
        "ppt_desc": "🔴 问题描述:",
        "ppt_business_impact": "📉 商业与 SEO 影响:", # New Header
        "ppt_sugg": "✅ 修复建议:",
        "ppt_examples": "🔍 示例:",
        "ppt_prev": "⬅️ 上一页",
        "ppt_next": "下一页 ➡️",
        
        # Categories (Removed Numbers for Dynamic Logic)
        "cat_access": "可访问性与索引 (Access & Indexing)",
        "cat_indexability": "索引规范性 (Indexability)",
        "cat_technical": "技术与架构 (Technical SEO)",
        "cat_content": "页面内容 (On-Page Content)",
        "cat_image_ux": "体验与资源 (UX & Assets)",

        # PPT Static Text
        "ppt_cover_title": "SEO 深度技术审计报告",
        "ppt_cover_sub": "Generated by AuditAI Pro v3.8",
        "ppt_slide_desc_title": "深度分析",
        "ppt_slide_count_title": "样本中受影响页面数: {} 个",
        "ppt_slide_ex_title": "受影响页面示例 & 可视化",
        "ppt_slide_sugg_title": "💡 修复建议:",
        "serp_sim_title": "Google 搜索结果模拟 (SERP):",
        "rich_sim_title": "富媒体结果模拟 (Rich Results):",

        # --- Issues ---
        "no_robots": "缺失 Robots.txt",
        "no_robots_desc": "无法访问 robots.txt 文件。",
        "no_robots_impact": "爬虫可能抓取无用页面，消耗服务器资源，且无法有效分配爬取预算。",
        "no_robots_sugg": "确保 robots.txt 文件存在且可公开访问。",
        
        "robots_bad_rule": "Robots.txt 规则风险",
        "robots_desc": "检测到封禁规则可能阻止搜索引擎抓取全站内容。",
        "robots_impact": "导致网站无法被收录，流量直接归零。",
        
        "robots_no_sitemap": "Robots.txt 未声明 Sitemap",
        "robots_no_sitemap_desc": "Sitemap 位置未在 robots.txt 中指明。",
        "robots_no_sitemap_impact": "降低搜索引擎发现新页面和更新内容的效率。",
        
        "no_sitemap": "Sitemap 访问失败",
        "no_sitemap_desc": "无法访问 Sitemap 文件。",
        "no_sitemap_impact": "搜索引擎难以发现深层页面，影响收录率。",
        
        "sitemap_invalid": "Sitemap 格式错误",
        "sitemap_invalid_desc": "XML 解析失败，格式不符合标准。",
        "sitemap_invalid_impact": "搜索引擎无法读取链接，导致 Sitemap 失效。",
        
        "no_favicon": "站点缺失 Favicon",
        "no_favicon_desc": "未在首页检测到 Favicon。",
        "no_favicon_impact": "降低品牌辨识度，直接导致搜索结果页 (SERP) 的用户点击率 (CTR) 下降。",

        "duplicate": "发现未规范化的重复内容", 
        "duplicate_desc": "内容高度重复且未指向同一 Canonical URL。", 
        "duplicate_impact": "导致关键词内部竞争 (Cannibalization)，分散页面权重，降低整体排名。",
        "duplicate_sugg": "使用 Canonical 指向原始页面。",
        
        "3xx_title": "内部链接重定向 (3xx)",
        "3xx_desc": "内部链接发生跳转。",
        "3xx_impact": "浪费爬虫预算，增加页面加载延迟，损耗链接传递的权重 (Link Equity)。",
        
        "4xx_title": "死链/客户端错误 (4xx)",
        "4xx_desc": "内部链接返回 4xx 错误 (如 404)。",
        "4xx_impact": "严重破坏用户体验，中断权重传递，导致索引页面被移除。",
        
        "5xx_title": "服务器错误 (5xx)",
        "5xx_desc": "服务器返回 5xx 错误。",
        "5xx_impact": "表明服务器不稳定，Googlebot 会降低该站点的爬取频率。",

        "hreflang_invalid": "Hreflang 代码格式错误",
        "hreflang_invalid_desc": "语言代码不符合 ISO 639-1 标准。",
        "hreflang_invalid_impact": "Google 无法识别目标语言，导致国际化定位失效。",
        
        "hreflang_no_default": "Hreflang 缺失 x-default",
        "hreflang_no_default_desc": "未配置 'x-default' 回退版本。",
        "hreflang_no_default_impact": "非匹配地区用户可能看到错误的语言版本，增加跳出率。",
        
        "alt_bad_quality": "图片 Alt 质量差",
        "alt_bad_quality_desc": "Alt 文本包含无意义词汇或过短。",
        "alt_bad_quality_impact": "错失图片搜索流量，且对视障用户不友好。",
        
        "anchor_bad_quality": "锚文本质量差 (Generic Anchor)",
        "anchor_bad_quality_desc": "使用了通用词汇（如 'Click here'）。",
        "anchor_bad_quality_impact": "无法向搜索引擎传递目标页面的关键词相关性。",
        
        "cls_risk": "存在 CLS 布局偏移风险 (CWV)",
        "cls_risk_desc": "检测到 img 标签缺失 width 或 height 属性。",
        "cls_risk_impact": "页面加载时发生抖动，导致 Core Web Vitals 不达标，直接影响排名。",
        
        "missing_title": "缺失页面标题 (Title)", 
        "missing_title_desc": "页面没有 <title> 标签。",
        "missing_title_impact": "这是最重要的 SEO 标签。缺失将导致搜索引擎无法判断页面主题，关键词排名极差。",
        
        "short_title": "标题过短", 
        "short_title_desc": "标题过短，难以覆盖核心关键词。",
        "short_title_impact": "浪费了宝贵的标题空间，错失长尾词排名机会。",
        
        "long_title": "标题过长", 
        "long_title_desc": "标题过长 (>60字符)。",
        "long_title_impact": "在搜索结果中会被截断 (...)，降低用户点击欲望。",
        
        "missing_desc": "缺失元描述", 
        "missing_desc_desc": "缺失 Meta Description。",
        "missing_desc_impact": "虽然不直接影响排名，但 Google 会随机抓取正文作为摘要，通常不可控且点击率低。",
        
        "short_desc": "元描述过短", 
        "short_desc_desc": "内容过少，吸引力不足。",
        "short_desc_impact": "无法充分展示页面卖点，降低 CTR。",
        
        "missing_h1": "缺失 H1 标签", 
        "missing_h1_desc": "页面缺乏 H1 主标题。",
        "missing_h1_impact": "搜索引擎难以理解内容的层级结构和核心主题。",
        
        "missing_viewport": "缺失移动端视口配置", 
        "missing_viewport_desc": "未配置 Viewport Meta 标签。",
        "missing_viewport_impact": "在移动设备上显示异常（字体极小）。Google 移动优先索引会严重惩罚此类页面。",
        
        "missing_canonical": "缺失 Canonical 标签", 
        "missing_canonical_desc": "未指定规范链接。",
        "missing_canonical_impact": "无法应对 URL 参数（如 ?id=1），导致严重的重复内容收录和权重稀释。",
        
        "missing_jsonld": "缺失结构化数据", 
        "missing_jsonld_desc": "未检测到 Schema 标记。",
        "missing_jsonld_impact": "错失富媒体搜索结果（Rich Results），在 SERP 中不如竞争对手显眼。",
        "missing_jsonld_sugg": "根据页面类型添加 JSON-LD：\n- 产品页: Product (显示价格、库存)\n- 文章页: Article\n- 首页: Organization",
        
        "missing_hreflang": "缺失 Hreflang", 
        "missing_hreflang_desc": "未发现语言区域标记。",
        "missing_hreflang_impact": "多语言站点无法正确定位目标受众，导致流量不精准。",
        
        "soft_404": "疑似软 404 (Soft 404)", 
        "soft_404_desc": "页面返回 200 但内容显示未找到。",
        "soft_404_impact": "严重浪费爬虫预算，导致无效页面挤占有效页面的索引名额。",
        
        "missing_alt": "图片缺失 Alt 属性", 
        "missing_alt_desc": "图片缺少替代文本。",
        "missing_alt_impact": "搜索引擎无法理解图片内容，错失图片搜索流量。",
        "missing_alt_sugg": "添加图片 alt 属性，描述图片内容。", # Added
        
        "js_links": "发现 JS 伪链接", 
        "js_links_desc": "href='javascript:' 爬虫无法抓取。",
        "js_links_impact": "导致内部链接断裂，权重无法传递，深层页面变成“孤岛”。",
        "js_links_sugg": "使用标准 <a href> 标签。", # Fixed: Added missing key
        
        "url_underscore": "URL 包含下划线", 
        "url_underscore_desc": "使用下划线分隔单词。",
        "url_underscore_impact": "Google 建议使用连字符。下划线可能导致关键词无法被正确切分。",
        
        "url_uppercase": "URL 包含大写字母", 
        "url_uppercase_desc": "URL 混用大小写。",
        "url_uppercase_impact": "服务器通常区分大小写，极易造成一页多址（Duplicate Content）。"
    },
    "en": {
        "sidebar_title": "🔍 AuditAI Pro",
        "sidebar_caption": "Deep Audit Edition v3.8.2",
        "nav_label": "Navigation",
        "nav_options": ["Input URL", "Dashboard", "Data Matrix", "PPT Generator"],
        "lang_label": "Language / 语言",
        "clear_data": "Clear Data & Reset",
        "cache_info": "Cached {} pages",
        "sitemap_status_title": "Sitemap Status:",
        "sitemap_found_href": "✅ Hreflang Found", 
        "sitemap_no_href": "⚠️ No Hreflang",       
        "sitemap_missing": "❌ Sitemap Missing",
        
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
        "ppt_cover_sub": "Generated by AuditAI Pro v3.8",
        "ppt_slide_desc_title": "Description & Impact",
        "ppt_slide_count_title": "Affected Pages (in sample): {}",
        "ppt_slide_ex_title": "Example URLs & Evidence",
        "ppt_slide_sugg_title": "💡 Recommendation:",
        "serp_sim_title": "Google SERP Simulation:",
        "rich_sim_title": "Rich Results Simulation:",

        # --- Issues ---
        "no_robots": "Missing Robots.txt", "no_robots_desc": "No robots.txt found.", "no_robots_impact": "Crawlers effectively blind.", 
        "robots_bad_rule": "Robots.txt Blocking", "robots_desc": "Blocking all agents.", "robots_impact": "Site de-indexed.",
        "robots_no_sitemap": "Sitemap not in Robots", "robots_no_sitemap_desc": "No sitemap link.", "robots_no_sitemap_impact": "Slower discovery.",
        "no_sitemap": "Sitemap Failed", "no_sitemap_desc": "Access denied.", "no_sitemap_impact": "Poor indexing.",
        "sitemap_invalid": "Invalid Sitemap", "sitemap_invalid_desc": "XML Error.", "sitemap_invalid_impact": "Unreadable sitemap.",
        "no_favicon": "Missing Favicon", "no_favicon_desc": "No icon found.", "no_favicon_impact": "Lower CTR in SERP.",
        "duplicate": "Duplicate Content", "duplicate_desc": "Exact match found.", "duplicate_impact": "Keyword cannibalization.",
        "3xx_title": "Redirect Chain", "3xx_desc": "Internal redirect.", "3xx_impact": "Wasted budget & latency.",
        "4xx_title": "Broken Link", "4xx_desc": "4xx Error.", "4xx_impact": "Bad UX & equity loss.",
        "5xx_title": "Server Error", "5xx_desc": "5xx Error.", "5xx_impact": "Googlebot reduces crawl rate.",
        "hreflang_invalid": "Invalid Hreflang", "hreflang_invalid_desc": "Bad code.", "hreflang_invalid_impact": "Targeting failed.",
        "hreflang_no_default": "No x-default", "hreflang_no_default_desc": "Missing fallback.", "hreflang_no_default_impact": "Wrong language shown.",
        "alt_bad_quality": "Bad Alt Text", "alt_bad_quality_desc": "Generic text.", "alt_bad_quality_impact": "No image SEO value.",
        "anchor_bad_quality": "Bad Anchor", "anchor_bad_quality_desc": "Generic anchor.", "anchor_bad_quality_impact": "No keyword relevance.",
        "cls_risk": "CLS Risk", "cls_risk_desc": "Missing dim.", "cls_risk_impact": "Layout shifts & ranking drop.",
        "missing_title": "Missing Title", "missing_title_desc": "No title.", "missing_title_impact": "Severe ranking loss.",
        "short_title": "Title Short", "short_title_desc": "Too short.", "short_title_impact": "Missed keywords.",
        "long_title": "Title Long", "long_title_desc": "Too long.", "long_title_impact": "Truncated in SERP.",
        "missing_desc": "Missing Description", "missing_desc_desc": "No meta desc.", "missing_desc_impact": "Lower CTR.",
        "short_desc": "Description Short", "short_desc_desc": "Too thin.", "short_desc_impact": "Less appealing.",
        "missing_h1": "Missing H1", "missing_h1_desc": "No H1.", "missing_h1_impact": "Poor structure.",
        "missing_viewport": "No Viewport", "missing_viewport_desc": "Mobile unfriendly.", "missing_viewport_impact": "Mobile ranking drop.",
        "missing_canonical": "No Canonical", "missing_canonical_desc": "Missing tag.", "missing_canonical_impact": "Duplicate content risk.",
        "missing_jsonld": "No Schema", "missing_jsonld_desc": "No JSON-LD.", "missing_jsonld_impact": "No Rich Snippets.",
        "missing_jsonld_sugg": "Add JSON-LD schema (Product/Article).",
        "missing_hreflang": "No Hreflang", "missing_hreflang_desc": "Missing tags.", "missing_hreflang_impact": "Poor internationalization.",
        "soft_404": "Soft 404", "soft_404_desc": "Fake 200.", "soft_404_impact": "Wasted budget.",
        "missing_alt": "Missing Alt", "missing_alt_desc": "No alt text.", "missing_alt_impact": "Bad for Image SEO.", 
        "missing_alt_sugg": "Add descriptive alt attributes.", # Added
        "js_links": "JS Links", "js_links_desc": "Uncrawlable.", "js_links_impact": "Broken link graph.", "js_links_sugg": "Use standard <a href> links.", # Fixed: Added missing key
        "url_underscore": "URL Underscores", "url_underscore_desc": "Has _.", "url_underscore_impact": "Bad parsing.",
        "url_uppercase": "URL Uppercase", "url_uppercase_desc": "Has Upper.", "url_uppercase_impact": "Duplicate risk."
    }
}

# --- 4. 爬虫核心引擎 ---
def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except: return False

def get_content_hash(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def get_browser_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
    }

def fetch_psi_data(url, api_key):
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
        else: return {"error": f"API Error: {response.status_code}"}
    except Exception as e: return {"error": str(e)}

def check_site_level_assets(start_url, lang="zh", manual_robots=None, manual_sitemaps=None):
    issues = []
    sitemap_has_hreflang = False
    parsed_url = urlparse(start_url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    headers = get_browser_headers()
    t = TRANSLATIONS[lang]

    # Robots.txt
    robots_url = manual_robots if manual_robots else urljoin(base_url, "/robots.txt")
    try:
        r = requests.get(robots_url, headers=headers, timeout=10, allow_redirects=True, stream=True, verify=False)
        if r.status_code != 200:
            issues.append({"category": "access", "severity": "Medium", "title": t["no_robots"], "desc": t["no_robots_desc"], "impact": t["no_robots_impact"], "suggestion": t["no_robots_sugg"], "url": robots_url})
        else:
            content = r.text.lower()
            if "disallow: /" in content and "allow:" not in content:
                 issues.append({"category": "access", "severity": "Critical", "title": t["robots_bad_rule"], "desc": t["robots_desc"], "impact": t["robots_impact"], "suggestion": "Remove global disallow rule.", "url": robots_url})
            if "sitemap:" not in content:
                 issues.append({"category": "access", "severity": "Low", "title": t["robots_no_sitemap"], "desc": t["robots_no_sitemap_desc"], "impact": t["robots_no_sitemap_impact"], "suggestion": "Add 'Sitemap: [URL]' directive.", "url": robots_url})
        r.close()
    except: 
        issues.append({"category": "access", "severity": "Medium", "title": t["no_robots"], "desc": "Connection failed.", "impact": t["no_robots_impact"], "suggestion": "Check server config.", "url": robots_url})

    # Sitemap
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
                        issues.append({"category": "access", "severity": "Medium", "title": t["sitemap_invalid"], "desc": t["sitemap_invalid_desc"], "impact": t["sitemap_invalid_impact"], "suggestion": "Check XML syntax.", "url": sitemap_url})
            else:
                if manual_sitemaps:
                    issues.append({"category": "access", "severity": "Low", "title": t["no_sitemap"], "desc": f"{t['no_sitemap_desc']} (Status: {r.status_code})", "impact": t["no_sitemap_impact"], "suggestion": "Check URL.", "url": sitemap_url})
        except:
            if manual_sitemaps: issues.append({"category": "access", "severity": "Low", "title": t["no_sitemap"], "desc": "Connection failed.", "impact": t["no_sitemap_impact"], "suggestion": "Check URL.", "url": sitemap_url})

    if not any_sitemap_valid and not manual_sitemaps:
         issues.append({"category": "access", "severity": "Low", "title": t["no_sitemap"], "desc": t["no_sitemap_desc"], "impact": t["no_sitemap_impact"], "suggestion": "Ensure sitemap.xml exists.", "url": sitemap_urls_to_check[0]})

    return issues, sitemap_has_hreflang

def analyze_page(url, html_content, status_code, lang="zh", sitemap_has_hreflang=False):
    soup = BeautifulSoup(html_content, 'html.parser')
    issues = []
    t = TRANSLATIONS[lang]
    
    for script in soup(["script", "style"]): script.extract()
    text_content = soup.get_text().strip()
    content_hash = get_content_hash(text_content)

    # --- Technical ---
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
            issues.append({"category": "technical", "severity": "High", "title": t["hreflang_invalid"], "desc": f"{t['hreflang_invalid_desc']} ({', '.join(invalid_codes[:3])})", "impact": t["hreflang_invalid_impact"], "suggestion": "Use ISO 639-1 codes.", "url": url})
        if not has_x_default:
            issues.append({"category": "technical", "severity": "Low", "title": t["hreflang_no_default"], "desc": t["hreflang_no_default_desc"], "impact": t["hreflang_no_default_impact"], "suggestion": "Add hreflang='x-default'.", "url": url})
    elif not sitemap_has_hreflang:
        issues.append({"category": "technical", "severity": "Low", "title": t["missing_hreflang"], "desc": t["missing_hreflang_desc"], "impact": t["missing_hreflang_impact"], "suggestion": t["missing_hreflang_sugg"], "url": url})

    if not soup.find('meta', attrs={'name': 'viewport'}):
        issues.append({"category": "technical", "severity": "Critical", "title": t["missing_viewport"], "desc": t["missing_viewport_desc"], "impact": t["missing_viewport_impact"], "suggestion": t["missing_viewport_sugg"], "url": url})

    canonical_tag = soup.find('link', attrs={'rel': 'canonical'})
    canonical_url = canonical_tag['href'] if canonical_tag else None
    if not canonical_url:
        issues.append({"category": "indexability", "severity": "Medium", "title": t["missing_canonical"], "desc": t["missing_canonical_desc"], "impact": t["missing_canonical_impact"], "suggestion": t["missing_canonical_sugg"], "url": url})

    if not soup.find('script', type='application/ld+json'):
         # Smart Suggestion Logic
         parsed_u = urlparse(url)
         path = parsed_u.path.lower()
         spec_rec = "BreadcrumbList"
         if path == "/" or path == "": spec_rec = "Organization / WebSite"
         elif any(k in path for k in ["product", "shop", "item"]): spec_rec = "Product"
         elif any(k in path for k in ["blog", "news", "article"]): spec_rec = "Article"
         
         custom_sugg = f"{t['missing_jsonld_sugg']}\n(Detected type: {spec_rec})"
         issues.append({"category": "technical", "severity": "Medium", "title": t["missing_jsonld"], "desc": t["missing_jsonld_desc"], "impact": t["missing_jsonld_impact"], "suggestion": custom_sugg, "url": url})

    parsed_url = urlparse(url)
    path = parsed_url.path
    if '_' in path:
         issues.append({"category": "technical", "severity": "Low", "title": t["url_underscore"], "desc": t["url_underscore_desc"], "impact": t["url_underscore_impact"], "suggestion": t["url_underscore_sugg"], "url": url})
    if any(c.isupper() for c in path):
         issues.append({"category": "technical", "severity": "Medium", "title": t["url_uppercase"], "desc": t["url_uppercase_desc"], "impact": t["url_uppercase_impact"], "suggestion": t["url_uppercase_sugg"], "url": url})

    js_links = soup.find_all('a', href=lambda x: x and x.lower().startswith('javascript:'))
    if js_links:
        issues.append({"category": "technical", "severity": "High", "title": t["js_links"], "desc": t["js_links_desc"], "impact": t["js_links_impact"], "suggestion": t["js_links_sugg"], "url": url, "meta": f"Count: {len(js_links)}"})

    # --- UX & Assets ---
    images = soup.find_all('img')
    missing_alt = 0
    bad_alt_count = 0
    cls_risk_count = 0
    bad_keywords = ["image", "photo", "picture", "img", "untitled"]
    
    for img in images:
        alt = img.get('alt', '').strip()
        if not alt: missing_alt += 1
        else:
            if len(alt) < 3 or any(bk in alt.lower() for bk in bad_keywords): bad_alt_count += 1
        if not img.get('width') or not img.get('height'): cls_risk_count += 1

    if missing_alt > 0:
        issues.append({"category": "image_ux", "severity": "Medium", "title": t["missing_alt"], "desc": f"{missing_alt} {t['missing_alt_desc']}", "impact": t["missing_alt_impact"], "suggestion": t["missing_alt_sugg"], "url": url})
    if bad_alt_count > 0:
        issues.append({"category": "image_ux", "severity": "Low", "title": t["alt_bad_quality"], "desc": t["alt_bad_quality_desc"], "impact": t["alt_bad_quality_impact"], "suggestion": "Avoid generic keywords.", "url": url, "evidence": f"{bad_alt_count} poor alts"})
    if cls_risk_count > 0:
        issues.append({"category": "image_ux", "severity": "Medium", "title": t["cls_risk"], "desc": t["cls_risk_desc"], "impact": t["cls_risk_impact"], "suggestion": "Specify width/height.", "url": url, "evidence": f"{cls_risk_count} images"})

    links = soup.find_all('a', href=True)
    bad_anchors = ["click here", "read more", "learn more", "more", "here"]
    found_bad = []
    for link in links:
        at = link.get_text().strip().lower()
        if at in bad_anchors: found_bad.append(at)
    if found_bad:
        issues.append({"category": "image_ux", "severity": "Low", "title": t["anchor_bad_quality"], "desc": f"{t['anchor_bad_quality_desc']} ({len(found_bad)})", "impact": t["anchor_bad_quality_impact"], "suggestion": "Use descriptive keywords.", "url": url})

    # --- Content ---
    title_tag = soup.title
    title = title_tag.string.strip() if title_tag and title_tag.string else None
    if not title:
        issues.append({"category": "content", "severity": "High", "title": t["missing_title"], "desc": t["missing_title_desc"], "impact": t["missing_title_impact"], "suggestion": t["missing_title_sugg"], "url": url})
    elif len(title) < 10:
         issues.append({"category": "content", "severity": "Medium", "title": t["short_title"], "desc": t["short_title_desc"], "impact": t["short_title_impact"], "suggestion": t["short_title_sugg"], "url": url, "evidence": title})
    elif len(title) > 60:
         issues.append({"category": "content", "severity": "Low", "title": t["long_title"], "desc": t["long_title_desc"], "impact": t["long_title_impact"], "suggestion": t["long_title_sugg"], "url": url, "evidence": title})

    meta_desc = soup.find('meta', attrs={'name': 'description'})
    desc_content = meta_desc['content'].strip() if meta_desc and meta_desc.get('content') else None
    if not desc_content:
        issues.append({"category": "content", "severity": "High", "title": t["missing_desc"], "desc": t["missing_desc_desc"], "impact": t["missing_desc_impact"], "suggestion": t["missing_desc_sugg"], "url": url})
    elif len(desc_content) < 50:
        issues.append({"category": "content", "severity": "Low", "title": t["short_desc"], "desc": t["short_desc_desc"], "impact": t["short_desc_impact"], "suggestion": t["short_desc_sugg"], "url": url, "evidence": desc_content})

    h1 = soup.find('h1')
    if not h1: issues.append({"category": "content", "severity": "High", "title": t["missing_h1"], "desc": t["missing_h1_desc"], "impact": t["missing_h1_impact"], "suggestion": t["missing_h1_sugg"], "url": url})

    if status_code == 200:
        error_kws = ["page not found", "404 error", "页面未找到"]
        is_s404 = False
        if title and any(k in title.lower() for k in error_kws): is_s404 = True
        elif soup.find('h1') and any(k in soup.find('h1').get_text().lower() for k in error_kws): is_s404 = True
        if is_s404:
            issues.append({"category": "access", "severity": "Critical", "title": t["soft_404"], "desc": t["soft_404_desc"], "impact": t["soft_404_impact"], "suggestion": t["soft_404_sugg"], "url": url})

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
    
    def clean_url(u): return u.split('?')[0].split('#')[0]
    t = TRANSLATIONS[lang] # Global

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

            # 1. 3xx
            if response.history:
                all_issues.append({"category": "access", "severity": "Medium", "title": t["3xx_title"], "desc": f"{t['3xx_desc']} -> {current_url}", "impact": t["3xx_impact"], "suggestion": t["3xx_sugg"], "url": url})

            # 2. 4xx/5xx
            if final_status >= 400:
                is_5xx = final_status >= 500
                all_issues.append({"category": "access", "severity": "Critical" if is_5xx else "High", "title": t["5xx_title"] if is_5xx else t["4xx_title"], "desc": f"{t['5xx_desc'] if is_5xx else t['4xx_desc']} ({final_status})", "impact": t["5xx_impact"] if is_5xx else t["4xx_impact"], "suggestion": t["5xx_sugg"] if is_5xx else t["4xx_sugg"], "url": url})

            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' in content_type:
                page_data, page_issues, _ = analyze_page(current_url, response.content, final_status, lang=lang, sitemap_has_hreflang=sitemap_has_hreflang)
                
                if final_status == 200:
                    current_hash = page_data['Content_Hash']
                    current_canonical = page_data['Canonical']
                    current_clean = clean_url(current_url)
                    
                    if current_hash in seen_hashes:
                        original_url = seen_hashes[current_hash]
                        original_clean = clean_url(original_url)
                        
                        if len(current_url) < len(original_url) and '?' not in current_url and '?' in original_url:
                            seen_hashes[current_hash] = current_url
                        elif current_clean == original_clean:
                            pass 
                        else:
                            is_handled = current_canonical and current_canonical != current_url
                            if not is_handled:
                                page_issues.append({"category": "indexability", "severity": "High", "title": t["duplicate"], "desc": f"{t['duplicate_desc']} (vs {original_url})", "impact": t["duplicate_impact"], "suggestion": t["duplicate_sugg"], "url": current_url})
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
        if len(display_title) > 60 and ("Long" in issue_title or "过长" in issue_title): display_title = display_title[:55] + " ..."
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

    def draw_rich_snippet_preview(slide, url):
        # Draw Rich Snippet (Stars)
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(7), Inches(2), Inches(5.8), Inches(2.5))
        box.fill.solid()
        box.fill.fore_color.rgb = RGBColor(255, 255, 255)
        box.line.color.rgb = RGBColor(220, 220, 220)
        tf = box.text_frame
        tf.margin_left = Inches(0.2)
        tf.margin_top = Inches(0.2)
        
        p = tf.add_paragraph()
        p.text = f"{urlparse(url).netloc} › product"
        set_font(p.font, 12, False, RGBColor(32, 33, 36))
        
        p = tf.add_paragraph()
        p.space_before = Pt(5)
        p.text = "Product Name Example - Best Choice"
        set_font(p.font, 18, False, RGBColor(26, 13, 171)) 
        
        p = tf.add_paragraph()
        p.space_before = Pt(3)
        p.text = "★★★★★ Rating: 4.8 · $199.00 · In stock" # Rich Data
        set_font(p.font, 12, False, RGBColor(231, 113, 27)) # Orange
        
        p = tf.add_paragraph()
        p.space_before = Pt(3)
        p.text = "This is a product description showing rich data..."
        set_font(p.font, 14, False, RGBColor(77, 81, 86))
        
        label = slide.shapes.add_textbox(Inches(7), Inches(1.6), Inches(4), Inches(0.3))
        p = label.text_frame.add_paragraph()
        p.text = txt["rich_sim_title"]
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
        
        h_shape = slide.shapes.add_shape(1, 0, 0, Inches(13.333), Inches(1.2))
        h_shape.fill.solid()
        h_shape.fill.fore_color.rgb = RGBColor(240, 242, 246)
        
        h_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(10), Inches(0.8))
        p = h_box.text_frame.add_paragraph()
        p.text = issue['title']
        set_font(p.font, 32, True, RGBColor(50, 50, 50))
        
        sev_color = RGBColor(220, 53, 69) if issue['severity'] == "Critical" else RGBColor(253, 126, 20)
        sev_box = slide.shapes.add_textbox(Inches(11), Inches(0.35), Inches(2), Inches(0.5))
        p = sev_box.text_frame.add_paragraph()
        p.text = f"{issue['severity']}"
        p.alignment = PP_ALIGN.CENTER
        set_font(p.font, 18, True, sev_color)
        
        # Category Label
        cat_key = f"cat_{issue['category']}"
        cat_label = txt.get(cat_key, issue['category'].upper())
        cat_box = slide.shapes.add_textbox(Inches(0.5), Inches(1.3), Inches(4), Inches(0.4))
        p = cat_box.text_frame.add_paragraph()
        p.text = cat_label
        set_font(p.font, 14, True, RGBColor(0, 102, 204))

        # Desc
        d_title = slide.shapes.add_textbox(Inches(0.5), Inches(1.8), Inches(6), Inches(0.5))
        p = d_title.text_frame.add_paragraph()
        p.text = txt["ppt_desc"]
        set_font(p.font, 18, True, RGBColor(30, 30, 30))
        
        d_box = slide.shapes.add_textbox(Inches(0.5), Inches(2.3), Inches(6), Inches(1.2))
        tf = d_box.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
        p = tf.add_paragraph()
        p.text = issue['desc']
        set_font(p.font, 14, False, RGBColor(80, 80, 80))
        
        # Impact (New Section)
        i_title = slide.shapes.add_textbox(Inches(0.5), Inches(3.6), Inches(6), Inches(0.5))
        p = i_title.text_frame.add_paragraph()
        p.text = txt["ppt_business_impact"]
        set_font(p.font, 18, True, RGBColor(30, 30, 30))

        i_box = slide.shapes.add_textbox(Inches(0.5), Inches(4.1), Inches(6), Inches(1.2))
        tf = i_box.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
        p = tf.add_paragraph()
        p.text = issue['impact'] # Now strictly separate
        set_font(p.font, 14, False, RGBColor(220, 53, 69)) # Red text for impact

        # Visuals
        is_serp = any(k in issue['title'] for k in ["Title", "标题", "Meta", "元描述"])
        is_rich = any(k in issue['title'] for k in ["Schema", "Structured", "结构化"])
        
        ev = issue.get('example_evidence', '')
        ex_url = issue['examples'][0] if issue['examples'] else "example.com"
        
        if is_serp:
            draw_serp_preview(slide, issue['title'], ev, ex_url)
        elif is_rich:
            draw_rich_snippet_preview(slide, ex_url)
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

        # Suggestion
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
                    "category": i.get("category", "content"),
                    "impact": i.get("impact", "") # New field
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
                
                st.markdown(f"**{ui['ppt_desc']}**")
                st.write(s['desc'])
                
                st.markdown(f"**{ui['ppt_business_impact']}**") # New
                st.error(s['impact']) # Red text for impact
                
                st.info(f"{ui['ppt_sugg']} {s['suggestion']}")
            with c2:
                is_serp = any(k in s['title'] for k in ["Title", "标题", "Meta", "元描述"])
                is_rich = any(k in s['title'] for k in ["Schema", "Structured", "结构化"])
                
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
                elif is_rich:
                     st.markdown(f"**{ui.get('rich_sim_title', 'Rich Result Preview')}**")
                     st.markdown("""
                     <div style="font-family: Arial, sans-serif; border: 1px solid #dfe1e5; border-radius: 8px; padding: 15px; background: white; box-shadow: 0 1px 6px rgba(32,33,36,0.28);">
                        <div style="font-size: 14px; color: #202124;">example.com <span style="color: #5f6368">› product</span></div>
                        <div style="font-size: 20px; color: #1a0dab; margin-top: 5px;">Best Product - High Quality</div>
                        <div style="color: #e7711b; font-size: 14px;">★★★★★ <span style="color:#70757a">Rating: 4.8 · $199.00 · In stock</span></div>
                        <div style="font-size: 14px; color: #4d5156; margin-top: 3px;">This is a rich result enabled by Schema...</div>
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
