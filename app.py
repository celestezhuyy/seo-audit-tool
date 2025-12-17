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

# --- Level 0: 页面基础配置 (必须是第一个 st 命令) ---
st.set_page_config(
    page_title="NextGen SEO Auditor",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

# --- Level 1: 基础工具函数 ---
def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def get_content_hash(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def estimate_pixel_width(text, font_size=18):
    """估算文本在 Google SERP 中的像素宽度"""
    if not text: return 0
    width = 0
    for char in text:
        if ord(char) > 127: 
            width += font_size
        elif char.isupper():
            width += font_size * 0.7 
        else:
            width += font_size * 0.55 
    return width

def get_browser_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
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
            if not crux: return {"error": "No CrUX data available"}
            return {
                "LCP": crux.get('LARGEST_CONTENTFUL_PAINT_MS', {}).get('percentile', 0) / 1000,
                "CLS": crux.get('CUMULATIVE_LAYOUT_SHIFT_SCORE', {}).get('percentile', 0) / 100,
                "INP": crux.get('INTERACTION_TO_NEXT_PAINT', {}).get('percentile', 0),
                "FCP": crux.get('FIRST_CONTENTFUL_PAINT_MS', {}).get('percentile', 0) / 1000,
            }
        else: return {"error": f"API Error: {response.status_code}"}
    except Exception as e: return {"error": str(e)}

# --- Level 2: 排序与配置常量 ---
CATEGORY_ORDER = ["access", "indexability", "technical", "content", "image_ux", "cwv_performance"]
SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}

ISSUE_PRIORITY_LIST = [
    "no_robots", "robots_bad_rule", "robots_quality_issue", "baidu_robots_missing", "robots_no_sitemap", "no_sitemap", "sitemap_invalid",
    "http_5xx", "http_4xx", "soft_404", "http_3xx",
    "duplicate", "missing_canonical", "hreflang_invalid", "hreflang_no_default", "missing_hreflang",
    "missing_viewport", "missing_jsonld", "js_links", "url_underscore", "url_uppercase",
    "missing_baidu_stats", "missing_baidu_verify", "missing_applicable_device", "missing_no_transform",
    "missing_title", "short_title", "long_title", "missing_desc", "short_desc", "missing_h1", "missing_keywords", 
    "no_favicon", "missing_alt", "alt_bad_quality", "anchor_bad_quality", 
    "lcp_issue", "inp_issue", "cls_issue", "fcp_issue", "cls_risk"
]

def get_issue_priority(issue_id):
    try: return ISSUE_PRIORITY_LIST.index(issue_id)
    except ValueError: return 999 

# --- Level 3: 国际化字典 ---
TRANSLATIONS = {
    "zh": {
        "sidebar_title": "🔍 AuditAI Pro",
        "sidebar_caption": "旗舰审计版 v12.4",
        "nav_label": "功能导航",
        "nav_options": ["输入网址", "仪表盘", "数据矩阵", "PPT 生成器"],
        "lang_label": "语言 / Language",
        "clear_data": "清除数据并重置",
        "cache_info": "已缓存 {} 个页面",
        "sitemap_status_title": "Sitemap 状态:",
        "sitemap_found_href": "✅ 发现 Hreflang 配置", 
        "sitemap_no_href": "⚠️ 未发现 Hreflang",     
        "sitemap_missing": "❌ 未找到 Sitemap",

        "psi_settings": "Google PSI API 设置 (推荐)",
        "psi_api_key_label": "输入 Google PageSpeed API Key",
        "psi_api_help": "建议填入以获取 LCP/CLS/INP 真实数据。留空则只进行代码审计。",
        "psi_list_url_label": "产品列表页 URL (可选)",
        "psi_detail_url_label": "产品详情页 URL (可选)",
        "psi_get_key": "没有 API Key? [点击这里免费申请](https://developers.google.com/speed/docs/insights/v5/get-started)",
        "psi_fetching": "正在调用 Google API 获取 {} 数据...",
        "psi_success": "成功获取真实用户数据！",
        "psi_error": "API 调用失败或无 CrUX 数据",
        
        "input_header": "开始深度审计",
        "input_info": "说明: v12.4 修复了应用启动白屏问题，并包含百度 SEO 增强功能。",
        "input_label": "输入目标网址 (首页)",
        "input_placeholder": "https://example.com",
        "max_pages_label": "最大爬取页面数",
        "adv_settings": "高级设置 (Advanced Settings)", 
        "check_robots_label": "检查并遵循 Robots.txt 规则", 
        "crawl_sitemap_label": "自动抓取 Robots.txt 中的 Sitemap", 
        "baidu_mode_label": "启用百度 SEO 审计模式", 
        "allow_subdomains_label": "允许抓取子域名 (如 blog.site.com)",
        "allow_outside_folder_label": "允许抓取父级目录 (如从 /en/ 开始抓取 /fr/)",
        "manual_sitemaps": "手动 Sitemap 地址 (每行一个, 补充用)", 
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
        "ppt_info": "说明：生成的 PPT 已优化为 16:9 宽屏，包含增强版可视化预览。",
        "ppt_btn": "生成并下载美化版 .pptx",
        "ppt_preview_header": "网页版预览",
        "ppt_slide_title": "问题类型:",
        "ppt_category": "分类:",
        "ppt_severity": "严重程度:",
        "ppt_impact": "影响范围:",
        "ppt_impact_desc": "在已爬取样本中发现 **{}** 个页面。",
        "ppt_desc": "🔴 问题描述:",
        "ppt_business_impact": "📉 Business & SEO Impact:", 
        "ppt_sugg": "✅ 修复建议:",
        "ppt_examples": "🔍 受影响页面示例:",
        "ppt_prev": "⬅️ 上一页",
        "ppt_next": "下一页 ➡️",
        
        "cat_access": "可访问性与索引 (Access & Indexing)",
        "cat_indexability": "索引规范性 (Indexability)",
        "cat_technical": "技术与架构 (Technical SEO)",
        "cat_content": "页面内容 (On-Page Content)",
        "cat_image_ux": "用户体验与资源 (UX & Assets)",
        "cat_cwv_performance": "核心性能指标 (Core Web Vitals)",

        "ppt_cover_title": "SEO 深度技术审计报告",
        "ppt_cover_sub": "Generated by AuditAI Pro v12.4",
        "ppt_slide_desc_title": "深度分析",
        "ppt_slide_count_title": "样本中受影响页面数: {} 个",
        "ppt_slide_ex_title": "受影响页面示例", 
        "ppt_slide_sugg_title": "💡 修复建议:",
        "serp_sim_title": "Google 搜索结果模拟 (SERP):",
        "rich_sim_title": "富媒体结果模拟 (Rich Results):",
        "code_sim_title": "代码片段示例 (Code Snippet):",
        "visual_sim_title": "视觉体验模拟:",
        "cwv_sim_title": "CWV 性能仪表盘 (Performance):",

        # Issues
        "lcp_issue": "LCP (最大内容绘制) 超标", "lcp_issue_desc": "LCP 时间为 {:.2f}s (目标 <2.5s)。页面主要内容加载过于缓慢。", "lcp_issue_impact": "LCP 是 Google 核心排名因素。加载缓慢会导致用户跳出率飙升，并直接降低在移动端的搜索排名。", "lcp_issue_sugg": "压缩图片体积（使用 WebP），使用 CDN 分发内容，推迟非关键 JS 执行，并预加载 LCP 关键元素。",
        "cls_issue": "CLS (累积布局偏移) 超标", "cls_issue_desc": "页面加载过程中元素发生意外位移 (Score > 0.1)。", "cls_issue_impact": "作为核心排名因素，布局不稳定会导致用户误触广告或按钮，严重损害品牌信誉和用户体验。", "cls_issue_sugg": "为所有图片和视频元素指定明确的宽度和高度属性，避免在顶部动态插入内容。",
        "inp_issue": "INP (交互到绘制延迟) 超标", "inp_issue_desc": "用户点击按钮后，页面响应延迟超过 200ms。", "inp_issue_impact": "Google 新引入的核心指标。高延迟会让用户觉得网站“卡顿”或无响应，严重影响转化率。", "inp_issue_sugg": "减少主线程阻塞，将长任务 (Long Tasks) 拆分为小任务，并优化复杂的 JavaScript 事件处理逻辑。",
        "fcp_issue": "FCP (首次内容绘制) 缓慢", "fcp_issue_desc": "FCP 时间为 {:.2f}s (目标 <1.8s)。用户看到页面第一个内容的时间过长。", "fcp_issue_impact": "FCP 慢会让用户感觉服务器响应迟钝，直接增加跳出率。", "fcp_issue_sugg": "优化服务器响应时间 (TTFB)，消除阻塞渲染的 CSS/JS 资源。",
        
        "no_robots": "缺失 Robots.txt", "no_robots_desc": "无法访问根目录的 robots.txt 文件，或者服务器返回错误状态码。", "no_robots_impact": "爬虫可能抓取无用的后台页面，不仅消耗服务器资源，还会浪费宝贵的爬取预算。", "no_robots_sugg": "在网站根目录创建标准的 robots.txt 文件，并确保其对搜索引擎爬虫公开可见。",
        "robots_bad_rule": "Robots.txt 封禁风险", "robots_bad_rule_desc": "检测到全站封禁规则 (Disallow: /)，且未发现针对 Googlebot 的例外规则。", "robots_bad_rule_impact": "这将直接导致搜索引擎停止抓取并索引您的网站，所有自然搜索流量将归零。", "robots_bad_rule_sugg": "立即移除 'Disallow: /' 规则，或者为搜索引擎爬虫添加具体的 'Allow' 规则。",
        "robots_quality_issue": "Robots.txt 规则配置不当", "robots_quality_issue_desc": "Robots.txt 文件存在潜在问题：{}。", "robots_quality_issue_impact": "可能导致Googlebot行为异常（如误判屏蔽或渲染失败）。", "robots_quality_issue_sugg": "检查 Robots.txt，移除废弃指令（如 Noindex），并确保允许访问 CSS/JS 资源。",
        "robots_no_sitemap": "Robots 未声明 Sitemap", "robots_no_sitemap_desc": "robots.txt 文件中未指明 Sitemap XML 文件的位置。", "robots_no_sitemap_impact": "会降低搜索引擎发现新页面和更新旧内容的速度，尤其对于大型网站影响更明显。", "robots_no_sitemap_sugg": "在 robots.txt 文件底部添加一行：Sitemap: https://yourdomain.com/sitemap.xml",
        "no_sitemap": "Sitemap 访问失败", "no_sitemap_desc": "无法访问 Sitemap 文件，服务器返回 4xx 或 5xx 错误。", "no_sitemap_impact": "搜索引擎难以发现深层链接或孤岛页面，导致整体收录率下降。", "no_sitemap_sugg": "检查 Sitemap 文件是否存在，以及服务器权限设置是否允许外部访问。",
        "sitemap_invalid": "Sitemap 格式错误", "sitemap_invalid_desc": "XML 解析失败，文件格式不符合标准协议。", "sitemap_invalid_impact": "搜索引擎无法读取其中的链接，导致 Sitemap 完全失效。", "sitemap_invalid_sugg": "使用 XML 验证工具检查文件语法，确保没有未闭合的标签或非法字符。",
        "no_favicon": "缺失 Favicon", "no_favicon_desc": "未在首页检测到 Favicon 图标。", "no_favicon_impact": "降低品牌在浏览器标签页和搜索结果页 (SERP) 中的辨识度，进而导致点击率 (CTR) 下降。", "no_favicon_sugg": "制作一个 .ico 或 .png 格式的图标，并在 <head> 中通过 <link rel='icon'> 引用。",
        "duplicate": "发现未规范化的重复内容", "duplicate_desc": "检测到高度相似的内容页面，且未正确配置 Canonical 标签。", "duplicate_impact": "导致关键词内部竞争 (Cannibalization)，分散页面权重，使所有相关页面都难以获得高排名。", "duplicate_sugg": "保留一个首选 URL，并在其他副本页面上添加 rel='canonical' 指向该首选 URL。",
        "http_3xx": "内部链接重定向 (3xx)", "http_3xx_desc": "内部链接发生跳转 (链条: {})。", "http_3xx_impact": "浪费爬虫预算，增加页面加载延迟，且每次跳转都会损耗少量链接传递的权重 (Link Equity)。", "http_3xx_sugg": "批量更新内部链接，使其直接指向最终的目标 URL，避免中间跳转。",
        "http_4xx": "死链/客户端错误 (4xx)", "http_4xx_desc": "内部链接返回 404 (未找到) 或 403 (禁止访问) 错误。", "http_4xx_impact": "严重破坏用户体验，中断权重传递路径，并可能导致已索引的页面被 Google 移除。", "http_4xx_sugg": "移除死链，或者将其重定向到最相关的有效页面。",
        "http_5xx": "服务器错误 (5xx)", "http_5xx_desc": "服务器响应 500/502/503 等内部错误。", "http_5xx_impact": "表明服务器极其不稳定，Googlebot 会因此降低对该站点的爬取频率以减轻负载。", "http_5xx_sugg": "检查服务器错误日志，优化数据库查询或升级服务器配置。",
        "hreflang_invalid": "Hreflang 格式错误", "hreflang_invalid_desc": "语言代码不符合 ISO 639-1 标准 (如使用了 {} 等错误格式)。", "hreflang_invalid_impact": "Google 无法识别目标语言，导致国际化定位失效。", "hreflang_invalid_sugg": "使用标准的 ISO 语言代码 (例如 'en-US' 而不是 'en_US')。",
        "hreflang_no_default": "Hreflang 缺失 x-default", "hreflang_no_default_desc": "未配置 'x-default' 回退版本。", "hreflang_no_default_impact": "当用户来自未指定的语言/地区时，可能无法自动匹配到最合适的通用版本（通常是英语）。", "hreflang_no_default_sugg": "添加 hreflang='x-default' 标签，指定默认的语言版本。",
        "alt_bad_quality": "图片 Alt 质量差", "alt_bad_quality_desc": "Alt 文本使用了无意义词汇（如 image1.jpg, photo）或过短。", "alt_bad_quality_impact": "搜索引擎无法理解图片内容，错失图片搜索流量，且对视障用户极不友好。", "alt_bad_quality_sugg": "使用描述性文本准确描述图片内容，包含相关的关键词。",
        "anchor_bad_quality": "锚文本质量差", "anchor_bad_quality_desc": "使用了“点击这里”、“更多”等通用词汇作为链接文本。", "anchor_bad_quality_impact": "无法向搜索引擎传递目标页面的关键词相关性，降低了目标页面的排名潜力。", "anchor_bad_quality_sugg": "使用描述性 keywords in the anchor text.",
        "cls_risk": "CLS 布局偏移风险 (静态检测)", "cls_risk_desc": "检测到 <img> 标签缺失 width 或 height 属性。", "cls_risk_impact": "图片加载时会撑开页面，导致布局发生意外抖动，直接恶化 CLS 指标。", "cls_risk_sugg": "在 HTML 中显式指定图片和视频的宽度和高度属性。",
        "missing_title": "缺失页面标题 (Title)", "missing_title_desc": "页面代码中未找到 <title> 标签。", "missing_title_impact": "Title 是最重要的 SEO 标签。缺失将导致搜索引擎无法判断页面主题，关键词排名极差。", "missing_title_sugg": "为每个页面添加独特、包含核心关键词的标题。",
        "short_title": "标题过短", "short_title_desc": "标题长度不足 (约 {} px)，难以完整表达页面意图。", "short_title_impact": "浪费了宝贵的标题空间，错失了覆盖长尾关键词排名的机会。", "short_title_sugg": "丰富标题内容，加入品牌词或修饰词，建议长度在 285-575 px 之间。",
        "long_title": "标题过长", "long_title_desc": "标题超过建议显示宽度 (约 {} px)。", "long_title_impact": "标题将在搜索结果中被截断，降低可读性和点击率。", "long_title_sugg": "精简标题长度，将核心信息前置，控制在 600 px 以内。",
        "missing_desc": "缺失元描述", "missing_desc_desc": "页面未包含 <meta name='description'> 标签。", "missing_desc_impact": "虽然不直接影响排名，但 Google 会随机抓取正文作为摘要，通常不可控且点击率低。", "missing_desc_sugg": "添加吸引人的元描述，概括页面内容并包含号召性用语。",
        "short_desc": "元描述过短", "short_desc_desc": "内容过少 (约 {} px)，吸引力不足。", "short_desc_impact": "无法充分展示页面卖点，在搜索结果中缺乏竞争力。", "short_desc_sugg": "扩充描述至 400-920 px，提供更多有价值的信息。",
        "missing_h1": "缺失 H1 标签", "missing_h1_desc": "页面缺乏 <h1> 主标题。", "missing_h1_impact": "搜索引擎难以理解内容的层级结构和核心主题，降低了关键词的相关性权重。", "missing_h1_sugg": "确保每个页面有且仅有一个 H1 标签，概括当前页面的主题。",
        "missing_viewport": "缺失移动端视口配置", "missing_viewport_desc": "未配置 <meta name='viewport'> 标签。", "missing_viewport_impact": "在移动设备上显示异常（字体极小）。Google 移动优先索引会严重惩罚此类页面。", "missing_viewport_sugg": "在 <head> 中添加标准的 viewport meta 标签。",
        "missing_canonical": "缺失 Canonical 标签", "missing_canonical_desc": "未指定规范链接。", "missing_canonical_impact": "无法应对 URL 参数（如 ?id=1）导致的重复内容问题，容易造成权重稀释。", "missing_canonical_sugg": "在所有页面添加自引用（Self-referencing）或指向原件的 Canonical 标签。",
        "missing_jsonld": "缺失结构化数据", "missing_jsonld_desc": "未检测到 Schema.org 标记。", "missing_jsonld_impact": "错失富媒体搜索结果（Rich Results），在 SERP 中不如竞争对手显眼。", "missing_jsonld_sugg": "建议配置结构化数据。基于页面内容，推荐添加：{}。",
        "missing_hreflang": "缺失 Hreflang", "missing_hreflang_desc": "未发现语言区域标记（HTML或Sitemap中均无）。", "missing_hreflang_impact": "多语言站点无法正确定位目标受众，导致流量不精准。", "missing_hreflang_sugg": "在 HTML 头部或 Sitemap 中配置 hreflang 标签。",
        "soft_404": "疑似软 404 (Soft 404)", "soft_404_desc": "页面返回 200 状态码但内容显示“未找到”。", "soft_404_impact": "严重浪费爬虫预算，导致无效页面挤占有效页面的索引名额。", "soft_404_sugg": "配置服务器对不存在的页面返回 404 HTTP 状态码。",
        "missing_alt": "图片缺失 Alt 属性", "missing_alt_desc": "图片标签缺少 alt 属性。", "missing_alt_impact": "搜索引擎无法理解图片内容，错失图片搜索流量。", "missing_alt_sugg": "为所有有意义的图片添加描述性的 alt 属性。",
        "js_links": "发现 JS 伪链接", "js_links_desc": "使用了 href='javascript:...' 形式的链接。", "js_links_impact": "爬虫无法跟踪此类链接，导致内部链接断裂，深层页面变成“孤岛”。", "js_links_sugg": "使用标准的 <a href> 标签，仅在 onclick 事件中处理 JS 逻辑。",
        "url_underscore": "URL 包含下划线", "url_underscore_desc": "URL 路径中使用下划线 (_) 分隔单词。", "url_underscore_impact": "Google 建议使用连字符。下划线可能导致关键词无法被正确切分（被视为一个长单词）。", "url_underscore_sugg": "在 URL 结构中使用连字符 (-) 代替下划线。",
        "url_uppercase": "URL 包含大写字母", "url_uppercase_desc": "URL 路径中混用了大写字母。", "url_uppercase_impact": "服务器通常区分大小写，极易造成一页多址（Duplicate Content）和 404 错误。", "url_uppercase_sugg": "强制所有 URL 使用小写字母。",
        
        # Baidu specific
        "missing_keywords": "Missing Meta Keywords (Baidu)",
        "missing_keywords_desc": "No <meta name='keywords'> tag found.",
        "missing_keywords_impact": "Baidu still uses keywords as a ranking signal, unlike Google.",
        "missing_keywords_sugg": "Add meta keywords tag with 3-5 relevant keywords.",
        "missing_baidu_stats": "Missing Baidu Analytics",
        "missing_baidu_stats_desc": "Baidu Tongji script (hm.baidu.com) not found.",
        "missing_baidu_stats_impact": "Unable to track Baidu traffic effectively.",
        "missing_baidu_stats_sugg": "Install Baidu Tongji script.",
        "missing_baidu_verify": "Missing Baidu Verification",
        "missing_baidu_verify_desc": "No 'baidu-site-verification' tag found.",
        "missing_baidu_verify_impact": "May delay site indexing on Baidu.",
        "missing_baidu_verify_sugg": "Add verification tag.",
        "baidu_robots_missing": "Missing Baidu Rules",
        "baidu_robots_missing_desc": "No specific rules for 'Baiduspider' in Robots.txt.",
        "baidu_robots_missing_impact": "Inefficient crawling by Baidu.",
        "baidu_robots_missing_sugg": "Add User-agent: Baiduspider directives.",
        "missing_applicable_device": "Missing Applicable Device (Baidu)",
        "missing_applicable_device_desc": "Meta tag 'applicable-device' not found.",
        "missing_applicable_device_impact": "Baidu can't identify if page is PC/Mobile adapted.",
        "missing_applicable_device_sugg": "Add <meta name='applicable-device' content='pc,mobile'>.",
        "missing_no_transform": "Missing No-transform (Baidu)",
        "missing_no_transform_desc": "Cache-Control: no-transform not found.",
        "missing_no_transform_impact": "Baidu might transcode your page (Siteapp), breaking layout.",
        "missing_no_transform_sugg": "Add <meta http-equiv='Cache-Control' content='no-transform'>."
    }
}

# --- 6. 核心逻辑 (Data Layer) ---
def get_translated_text(issue_id, lang, args=None):
    if args is None: args = []
    t = TRANSLATIONS[lang]
    
    def safe_format(text, arguments):
        try: return text.format(*arguments)
        except IndexError: return text

    return {
        "title": t.get(issue_id, issue_id),
        "desc": safe_format(t.get(issue_id + "_desc", ""), args),
        "impact": t.get(issue_id + "_impact", ""),
        "suggestion": safe_format(t.get(issue_id + "_sugg", ""), args)
    }

def fetch_psi_data(url, api_key):
    if not api_key: return None
    endpoint = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&key={api_key}&strategy=mobile"
    try:
        response = requests.get(endpoint, timeout=30)
        if response.status_code == 200:
            data = response.json()
            crux = data.get('loadingExperience', {}).get('metrics', {})
            if not crux: return {"error": "No CrUX data available"}
            return {
                "LCP": crux.get('LARGEST_CONTENTFUL_PAINT_MS', {}).get('percentile', 0) / 1000,
                "CLS": crux.get('CUMULATIVE_LAYOUT_SHIFT_SCORE', {}).get('percentile', 0) / 100,
                "INP": crux.get('INTERACTION_TO_NEXT_PAINT', {}).get('percentile', 0),
                "FCP": crux.get('FIRST_CONTENTFUL_PAINT_MS', {}).get('percentile', 0) / 1000,
            }
        else: return {"error": f"API Error: {response.status_code}"}
    except Exception as e: return {"error": str(e)}

def check_cwv_issues(cwv_data, url, label=""):
    issues = []
    if not cwv_data or "error" in cwv_data: return issues
    category_key = "cwv_performance"
    
    # Thresholds
    # LCP: Good < 2.5, Poor > 4.0
    lcp = cwv_data.get("LCP", 0)
    if lcp > 2.5:
        issues.append({
            "id": "lcp_issue", "category": category_key, "severity": "Critical" if lcp > 4.0 else "High",
            "url": url, "args": [lcp], "examples": [f"{url} ({lcp:.2f}s) {label}"] 
        })
    
    # INP: Good < 200, Poor > 500
    inp = cwv_data.get("INP", 0)
    if inp > 200:
        issues.append({
            "id": "inp_issue", "category": category_key, "severity": "Critical" if inp > 500 else "High",
            "url": url, "args": [inp], "examples": [f"{url} ({inp}ms) {label}"]
        })

    # CLS: Good < 0.1, Poor > 0.25
    cls = cwv_data.get("CLS", 0)
    if cls > 0.1:
        issues.append({
            "id": "cls_issue", "category": category_key, "severity": "Critical" if cls > 0.25 else "High",
            "url": url, "args": [cls], "examples": [f"{url} ({cls:.3f}) {label}"]
        })
    
    # FCP: Good <= 1.8
    fcp = cwv_data.get("FCP", 0)
    if fcp > 1.8:
        issues.append({
            "id": "fcp_issue", "category": category_key, "severity": "Critical" if fcp > 3.0 else "Medium",
            "url": url, "args": [fcp], "examples": [f"{url} ({fcp:.2f}s) {label}"]
        })

    return issues

def check_site_level_assets(start_url, lang="zh", check_robots=True, crawl_sitemap_flag=True, manual_sitemaps=None, baidu_mode=False):
    issues = []
    sitemap_has_hreflang = False
    
    initial_netloc = urlparse(start_url).netloc
    base_url = f"{urlparse(start_url).scheme}://{initial_netloc}"
    headers = get_browser_headers()
    
    # 1. Robots.txt Logic
    robots_url = urljoin(base_url, "/robots.txt")
    if check_robots:
        try:
            r = requests.get(robots_url, headers=headers, timeout=10, allow_redirects=True, stream=True, verify=False)
            if r.status_code != 200:
                issues.append({"id": "no_robots", "category": "access", "severity": "Medium", "url": robots_url, "examples": [robots_url]})
            else:
                content = r.text.lower()
                if len(content.strip()) < 5:
                     issues.append({"id": "robots_quality_issue", "category": "access", "severity": "Medium", "url": robots_url, "args": ["File is empty or too short"], "examples": [robots_url]})
                if "user-agent" not in content:
                     issues.append({"id": "robots_quality_issue", "category": "access", "severity": "Medium", "url": robots_url, "args": ["Missing User-agent directive"], "examples": [robots_url]})
                if "disallow: /*.css" in content or "disallow: /*.js" in content:
                     issues.append({"id": "robots_quality_issue", "category": "access", "severity": "High", "url": robots_url, "args": ["Blocking CSS/JS resources"], "examples": [robots_url]})
                
                if "disallow: /" in content and "allow:" not in content:
                    issues.append({"id": "robots_bad_rule", "category": "access", "severity": "Critical", "url": robots_url, "examples": [robots_url]})
                
                if baidu_mode:
                    if "baiduspider" not in content:
                        issues.append({"id": "baidu_robots_missing", "category": "access", "severity": "Low", "url": robots_url, "examples": [robots_url]})
                
                if "sitemap:" not in content:
                    issues.append({"id": "robots_no_sitemap", "category": "access", "severity": "Low", "url": robots_url, "examples": [robots_url]})
                
                # Auto-discover Sitemap
                if crawl_sitemap_flag:
                    sitemaps_in_robots = re.findall(r'sitemap:\s*(https?://\S+)', content, re.IGNORECASE)
                    if sitemaps_in_robots:
                        if manual_sitemaps is None: manual_sitemaps = []
                        manual_sitemaps.extend(sitemaps_in_robots)
            r.close()
        except: 
            issues.append({"id": "no_robots", "category": "access", "severity": "Medium", "url": robots_url, "examples": [robots_url]})

    # 2. Sitemap Logic
    sitemap_urls = manual_sitemaps if manual_sitemaps else [urljoin(base_url, "/sitemap.xml")]
    any_valid = False
    for sm_url in sitemap_urls:
        if not sm_url.strip(): continue
        try:
            r = requests.get(sm_url, headers=headers, timeout=15, verify=False)
            if r.status_code == 200:
                try:
                    ET.fromstring(r.content)
                    any_valid = True
                    if 'hreflang' in r.text or 'xhtml' in r.text: sitemap_has_hreflang = True
                except:
                    if not sm_url.endswith('.gz'):
                        issues.append({"id": "sitemap_invalid", "category": "access", "severity": "Medium", "url": sm_url, "examples": [sm_url]})
            else:
                if manual_sitemaps: issues.append({"id": "no_sitemap", "category": "access", "severity": "Low", "url": sm_url, "examples": [sm_url]})
        except:
            if manual_sitemaps: issues.append({"id": "no_sitemap", "category": "access", "severity": "Low", "url": sm_url, "examples": [sm_url]})

    if not any_valid and not manual_sitemaps:
         issues.append({"id": "no_sitemap", "category": "access", "severity": "Low", "url": sitemap_urls[0], "examples": [sitemap_urls[0]]})

    # 3. Favicon
    try:
        r = requests.get(urljoin(base_url, "/favicon.ico"), headers=headers, timeout=5, verify=False)
        if r.status_code != 200 or int(r.headers.get('content-length', 0)) == 0:
            issues.append({"id": "no_favicon", "category": "image_ux", "severity": "Low", "url": base_url, "examples": [base_url]})
    except: pass

    return issues, sitemap_has_hreflang

def analyze_page(url, content, status, sitemap_has_hreflang, baidu_mode=False):
    soup = BeautifulSoup(content, 'html.parser')
    issues = []
    
    title = soup.title.string.strip() if soup.title else None
    desc = soup.find('meta', attrs={'name': 'description'})
    desc_content = desc['content'].strip() if desc else None
    h1 = soup.find('h1')
    h1_content = h1.get_text().strip() if h1 else None
    
    can_tag = soup.find('link', attrs={'rel': 'canonical'})
    can_url = can_tag['href'] if can_tag else None

    if status == 200:
        is_self_canonical = True
        if can_url:
            def norm_u(u): return u.split('#')[0].rstrip('/')
            try:
                abs_can = urljoin(url, can_url)
                if norm_u(abs_can) != norm_u(url):
                    is_self_canonical = False
            except: pass

        if not can_url:
            issues.append({"id": "missing_canonical", "category": "indexability", "severity": "Medium", "url": url})
            is_self_canonical = True

        hreflangs = soup.find_all('link', hreflang=True)
        if hreflangs:
            has_x_default = False
            invalid = []
            pat = re.compile(r'^[a-z]{2}(-[a-zA-Z]{2})?$|x-default', re.IGNORECASE)
            for link in hreflangs:
                code = link.get('hreflang', '').strip()
                if code.lower() == 'x-default': has_x_default = True
                if not pat.match(code): invalid.append(code)
            if invalid:
                issues.append({"id": "hreflang_invalid", "category": "indexability", "severity": "High", "url": url, "args": [", ".join(invalid[:3])]})
            if not has_x_default:
                issues.append({"id": "hreflang_no_default", "category": "indexability", "severity": "Low", "url": url})
        elif not sitemap_has_hreflang:
             if is_self_canonical:
                issues.append({"id": "missing_hreflang", "category": "indexability", "severity": "Low", "url": url})

        if is_self_canonical:
            if not soup.find('meta', attrs={'name': 'viewport'}):
                issues.append({"id": "missing_viewport", "category": "technical", "severity": "Critical", "url": url})
            
            if not soup.find('script', type='application/ld+json'):
                 path = urlparse(url).path.lower()
                 rec = "BreadcrumbList"
                 if path in ["/", ""]: rec = "Organization/WebSite"
                 elif any(x in path for x in ["product", "shop"]): rec = "Product"
                 elif any(x in path for x in ["blog", "news"]): rec = "Article"
                 issues.append({"id": "missing_jsonld", "category": "technical", "severity": "Medium", "url": url, "args": [rec]})

            if '_' in url: issues.append({"id": "url_underscore", "category": "technical", "severity": "Low", "url": url})
            if any(c.isupper() for c in urlparse(url).path): issues.append({"id": "url_uppercase", "category": "technical", "severity": "Medium", "url": url})
            
            if soup.find('a', href=lambda x: x and x.lower().startswith('javascript:')):
                issues.append({"id": "js_links", "category": "access", "severity": "High", "url": url}) 

            imgs = soup.find_all('img')
            missing_alt = 0
            bad_alt = 0
            cls_risk = 0
            for img in imgs:
                alt = img.get('alt', '').strip()
                if not alt: missing_alt += 1
                elif len(alt) < 3 or any(x in alt.lower() for x in ["image", "photo", "img"]): bad_alt += 1
                if not img.get('width') or not img.get('height'): cls_risk += 1
            
            if missing_alt > 0: issues.append({"id": "missing_alt", "category": "image_ux", "severity": "Medium", "url": url})
            if bad_alt > 0: issues.append({"id": "alt_bad_quality", "category": "image_ux", "severity": "Low", "url": url})
            if cls_risk > 0: issues.append({"id": "cls_risk", "category": "cwv_performance", "severity": "Medium", "url": url})

            links = soup.find_all('a', href=True)
            bad_anchors = ["click here", "read more", "more"]
            if any(a.get_text().strip().lower() in bad_anchors for a in links):
                issues.append({"id": "anchor_bad_quality", "category": "access", "severity": "Low", "url": url})
            
            if not title: 
                issues.append({"id": "missing_title", "category": "content", "severity": "High", "url": url})
            else:
                px_w = estimate_pixel_width(title)
                if px_w < 200:
                    issues.append({"id": "short_title", "category": "content", "severity": "Medium", "url": url, "evidence": title, "args": [int(px_w)]})
                elif px_w > 600:
                    issues.append({"id": "long_title", "category": "content", "severity": "Low", "url": url, "evidence": title, "args": [int(px_w)]})

            if not desc_content: 
                issues.append({"id": "missing_desc", "category": "content", "severity": "High", "url": url})
            else:
                px_w_d = estimate_pixel_width(desc_content)
                if px_w_d < 400:
                    issues.append({"id": "short_desc", "category": "content", "severity": "Low", "url": url, "evidence": desc_content, "args": [int(px_w_d)]})

            if not h1_content: issues.append({"id": "missing_h1", "category": "content", "severity": "High", "url": url})

            if (title and "not found" in title.lower()) or (soup.find('h1') and "not found" in soup.find('h1').get_text().lower()):
                issues.append({"id": "soft_404", "category": "access", "severity": "Critical", "url": url})
        
        if baidu_mode:
            keywords = soup.find('meta', attrs={'name': 'keywords'})
            if not keywords or not keywords.get('content', '').strip():
                 issues.append({"id": "missing_keywords", "category": "content", "severity": "Medium", "url": url})
            
            if "hm.baidu.com" not in str(soup):
                 issues.append({"id": "missing_baidu_stats", "category": "technical", "severity": "Low", "url": url})
            
            if not soup.find('meta', attrs={'name': 'applicable-device'}):
                 issues.append({"id": "missing_applicable_device", "category": "technical", "severity": "Medium", "url": url})
            
            has_no_transform = False
            for meta in soup.find_all('meta'):
                if meta.get('http-equiv', '').lower() == 'cache-control' and 'no-transform' in meta.get('content', '').lower():
                    has_no_transform = True
                    break
            if not has_no_transform:
                 issues.append({"id": "missing_no_transform", "category": "technical", "severity": "Medium", "url": url})


    return {
        "URL": url, 
        "Status": status, 
        "Title": title, 
        "Description": desc_content,
        "H1": h1_content,
        "Canonical": can_url,
        "Content_Hash": hashlib.md5(soup.get_text().encode('utf-8')).hexdigest()
    }, issues

def crawl_website(start_url, max_pages, lang, manual_robots, manual_sitemaps, psi_key, list_url=None, detail_url=None, check_robots=True, crawl_sitemap=True, allow_sub=False, allow_outside=False, baidu_mode=False):
    visited = set()
    seen_hashes = {} 
    seen_urls = set()
    
    queue = [start_url]
    seen_urls.add(start_url)
    if list_url and is_valid_url(list_url):
         queue.append(list_url)
         seen_urls.add(list_url)
    if detail_url and is_valid_url(detail_url):
         queue.append(detail_url)
         seen_urls.add(detail_url)

    results_data = []
    all_issues = []
    first_error = None
    target_domain = None
    
    start_netloc = urlparse(start_url).netloc.replace('www.', '')
    start_path = urlparse(start_url).path
    if not start_path.endswith('/'): start_path += '/'
    
    def clean_url(u): return u.split('?')[0].split('#')[0]

    progress_bar = st.progress(0, text="Initializing...")
    sitemap_has_hreflang = False
    
    try:
        site_issues, sitemap_has_hreflang = check_site_level_assets(
            start_url, lang, check_robots, crawl_sitemap, manual_sitemaps, baidu_mode
        )
        all_issues.extend(site_issues)
        st.session_state['sitemap_hreflang_found'] = sitemap_has_hreflang
    except Exception as e:
        pass

    if psi_key:
        with st.spinner(TRANSLATIONS[lang]["psi_fetching"].format("Pages")):
            targets = [("Home", start_url)]
            if list_url and is_valid_url(list_url): targets.append(("List", list_url))
            if detail_url and is_valid_url(detail_url): targets.append(("Detail", detail_url))
            
            for label, t_url in targets:
                cwv_data = fetch_psi_data(t_url, psi_key)
                if cwv_data and "error" not in cwv_data:
                    if label == "Home": st.session_state['cwv_data'] = cwv_data
                    all_issues.extend(check_cwv_issues(cwv_data, t_url, label=f"({label})"))

    count = 0
    headers = get_browser_headers()
    
    while queue and count < max_pages:
        url = queue.pop(0)
        visited.add(url)
        
        if any(x in url.lower() for x in ['/login', '/signin', '/admin', '/cart', '/account']):
            continue

        count += 1
        progress_bar.progress(int(count/max_pages*100), text=f"Crawling ({count}/{max_pages}): {url}")
        time.sleep(0.1)
        
        try:
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True, verify=False)
            current_url = response.url 
            
            if count == 1 and url == start_url:
                 start_netloc = urlparse(current_url).netloc.replace('www.', '')

            final_status = response.status_code

            if response.history:
                chain_list = [r.url for r in response.history] + [current_url]
                origin_netloc = urlparse(chain_list[0]).netloc.replace('www.', '')
                chain_display_parts = []
                for u in chain_list:
                    u_obj = urlparse(u)
                    u_netloc = u_obj.netloc.replace('www.', '')
                    if u_netloc != origin_netloc:
                        chain_display_parts.append(u) 
                    else:
                        p = u_obj.path
                        if not p: p = "/"
                        chain_display_parts.append(p)

                chain_str = " -> ".join(chain_display_parts)
                all_issues.append({"id": "http_3xx", "category": "access", "severity": "Medium", "url": url, "args": [chain_str]})

            if final_status >= 400:
                is_5xx = final_status >= 500
                all_issues.append({"id": "http_5xx" if is_5xx else "http_4xx", "category": "access", "severity": "Critical" if is_5xx else "High", "url": url, "args": [str(final_status)]})

            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' in content_type:
                if 'type="password"' in response.text.lower():
                     continue

                page_data, page_issues = analyze_page(current_url, response.content, final_status, sitemap_has_hreflang, baidu_mode)
                
                if final_status == 200:
                    current_hash = page_data['Content_Hash']
                    current_canonical = page_data['Canonical']
                    current_clean = clean_url(current_url)
                    
                    if current_hash in seen_hashes:
                        original_url = seen_hashes[current_hash]
                        if current_url != original_url and not (current_canonical and current_canonical != current_url):
                            all_issues.append({
                                "id": "duplicate", "category": "indexability", 
                                "severity": "High", "url": current_url, 
                                "meta": original_url 
                            })
                    else:
                        seen_hashes[current_hash] = current_url

                results_data.append(page_data)
                all_issues.extend(page_issues)
                
                soup = BeautifulSoup(response.content, 'html.parser')
                for a in soup.find_all('a', href=True):
                    raw_link = urljoin(current_url, a['href'])
                    link = raw_link.split('#')[0] 
                    
                    link_parsed = urlparse(link)
                    link_netloc = link_parsed.netloc.replace('www.', '')
                    link_path = link_parsed.path

                    is_internal = False
                    if not link_netloc: is_internal = True
                    elif allow_sub:
                        is_internal = link_netloc.endswith(start_netloc)
                    else:
                        is_internal = link_netloc == start_netloc

                    path_ok = True
                    if not allow_outside:
                        if not link_path.startswith(start_path): path_ok = False
                    
                    if is_internal and path_ok and link not in seen_urls:
                        if not any(link.lower().endswith(ext) for ext in ['.jpg', '.png', '.pdf', '.zip', '.css', '.js', '.json', '.xml']):
                            seen_urls.add(link)
                            queue.append(link)
            else:
                if count == 1: first_error = f"Content type: {content_type}"
        except Exception as e:
            if count == 1: first_error = str(e)
            pass
    
    progress_bar.empty()
    if not results_data and first_error: return None, None, first_error
    return results_data, all_issues, None

def draw_cwv_gauge(slide, metric, value, thresholds):
    good, poor = thresholds
    total_w = 4
    x_start = 7.2
    y_pos = 4.8
    h = 0.4

    r1 = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x_start), Inches(y_pos), Inches(total_w/3), Inches(h))
    r1.fill.solid()
    r1.fill.fore_color.rgb = RGBColor(12, 206, 107)
    r1.line.fill.background()

    r2 = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x_start + total_w/3), Inches(y_pos), Inches(total_w/3), Inches(h))
    r2.fill.solid()
    r2.fill.fore_color.rgb = RGBColor(255, 164, 0)
    r2.line.fill.background()
    
    r3 = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x_start + 2*total_w/3), Inches(y_pos), Inches(total_w/3), Inches(h))
    r3.fill.solid()
    r3.fill.fore_color.rgb = RGBColor(255, 78, 66)
    r3.line.fill.background()
    
    def add_label(x_offset, text):
        tb = slide.shapes.add_textbox(Inches(x_start + x_offset - 0.2), Inches(y_pos + 0.40), Inches(0.5), Inches(0.3))
        tb.margin_top = 0
        p = tb.text_frame.add_paragraph()
        p.text = text
        p.font.size = Pt(9)
        p.font.color.rgb = RGBColor(80, 80, 80)

    add_label(0, "0")
    add_label(total_w/3, str(good))
    add_label(2*total_w/3, str(poor))

    pos = 0
    if value <= good:
        pos = (value / good) * (total_w/3)
    elif value <= poor:
        pos = (total_w/3) + ((value - good) / (poor - good)) * (total_w/3)
    else:
        cap = poor * 1.5
        normalized = min(value, cap)
        pos = (2*total_w/3) + ((normalized - poor) / (cap - poor)) * (total_w/3)

    marker_x = x_start + pos
    
    tri = slide.shapes.add_shape(MSO_SHAPE.ISOSCELES_TRIANGLE, Inches(marker_x - 0.1), Inches(y_pos - 0.2), Inches(0.2), Inches(0.2))
    tri.rotation = 180
    tri.fill.solid()
    tri.fill.fore_color.rgb = RGBColor(50, 50, 50)
    tri.line.fill.background()
    
    tb = slide.shapes.add_textbox(Inches(marker_x - 0.5), Inches(y_pos - 0.8), Inches(1), Inches(0.3))
    p = tb.text_frame.add_paragraph()
    p.text = f"{value}"
    p.font.size = Pt(11)
    p.font.bold = True
    p.alignment = PP_ALIGN.CENTER


def create_styled_pptx(slides_data, lang):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    txt = TRANSLATIONS[lang] 
    
    def set_font(font_obj, size, bold=False, color=None):
        font_obj.size = Pt(size)
        font_obj.name = 'Microsoft YaHei' if lang == "zh" else 'Arial'
        font_obj.bold = bold
        if color: font_obj.color.rgb = color

    def draw_serp_preview(slide, issue_id, issue_title, evidence, url):
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(7), Inches(4), Inches(5.8), Inches(1.8))
        box.fill.solid()
        box.fill.fore_color.rgb = RGBColor(255, 255, 255)
        box.line.color.rgb = RGBColor(220, 220, 220)
        
        label = slide.shapes.add_textbox(Inches(7), Inches(3.6), Inches(4), Inches(0.3))
        p = label.text_frame.add_paragraph()
        
        if "favicon" in issue_id:
             p.text = txt["visual_sim_title"]
             set_font(p.font, 12, True, RGBColor(100, 100, 100))
             circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(7.2), Inches(4.3), Inches(0.25), Inches(0.25))
             circle.fill.solid()
             circle.fill.fore_color.rgb = RGBColor(200, 200, 200) 
             l1 = slide.shapes.add_shape(MSO_SHAPE.ARC, Inches(7.2), Inches(4.3), Inches(0.25), Inches(0.25))
             l1.line.color.rgb = RGBColor(150, 150, 150)
             l2 = slide.shapes.add_shape(MSO_SHAPE.CONNECTOR_STRAIGHT, Inches(7.325), Inches(4.3), Inches(7.325), Inches(4.55))
             l2.line.color.rgb = RGBColor(150, 150, 150)

             tb = slide.shapes.add_textbox(Inches(7.5), Inches(4.25), Inches(4), Inches(0.4))
             p2 = tb.text_frame.add_paragraph()
             p2.text = urlparse(url).netloc
             set_font(p2.font, 12, False, RGBColor(32, 33, 36))
             
             tb_t = slide.shapes.add_textbox(Inches(7.2), Inches(4.6), Inches(5), Inches(0.4))
             p_t = tb_t.text_frame.add_paragraph()
             p_t.text = "Page Title Example"
             set_font(p_t.font, 16, False, RGBColor(26, 13, 171))
             
             tb_d = slide.shapes.add_textbox(Inches(7.2), Inches(5.0), Inches(5), Inches(0.4))
             p_d = tb_d.text_frame.add_paragraph()
             p_d.text = "This simulates a missing favicon result on Google mobile SERP."
             set_font(p_d.font, 12, False, RGBColor(80, 80, 80))

        elif "alt" in issue_id:
             p.text = "Screen Reader View:"
             set_font(p.font, 12, True, RGBColor(100, 100, 100))
             
             img_box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(7.2), Inches(4.2), Inches(1.5), Inches(1.0))
             img_box.line.color.rgb = RGBColor(100, 100, 100)
             img_box.fill.background() 
             
             bubble_text = '<img src="..." />'
             color = RGBColor(200, 0, 0)
             if "quality" in issue_id:
                 bubble_text = '<img src="..." alt="image" />'
                 color = RGBColor(255, 165, 0)
             
             callout = slide.shapes.add_shape(MSO_SHAPE.LINE_CALLOUT_2, Inches(8.8), Inches(4.2), Inches(3.5), Inches(0.8))
             callout.fill.solid()
             callout.fill.fore_color.rgb = RGBColor(240, 240, 240)
             callout.text_frame.text = bubble_text
             callout.text_frame.paragraphs[0].font.color.rgb = color
             
        elif "lcp" in issue_id:
             p.text = txt["cwv_sim_title"] + " LCP"
             set_font(p.font, 12, True, RGBColor(100, 100, 100))
             val = float(re.findall(r"(\d+\.\d+)", evidence)[0]) if re.findall(r"(\d+\.\d+)", evidence) else 3.0
             draw_cwv_gauge(slide, "LCP", val, (2.5, 4.0))

        elif "inp" in issue_id:
             p.text = txt["cwv_sim_title"] + " INP"
             set_font(p.font, 12, True, RGBColor(100, 100, 100))
             val = float(re.findall(r"(\d+)", evidence)[0]) if re.findall(r"(\d+)", evidence) else 300
             draw_cwv_gauge(slide, "INP", val, (200, 500))

        elif "cls" in issue_id:
             p.text = txt["cwv_sim_title"] + " CLS"
             set_font(p.font, 12, True, RGBColor(100, 100, 100))
             val = float(re.findall(r"(\d+\.\d+)", evidence)[0]) if re.findall(r"(\d+\.\d+)", evidence) else 0.2
             draw_cwv_gauge(slide, "CLS", val, (0.1, 0.25))

        elif "fcp" in issue_id:
             p.text = txt["cwv_sim_title"] + " FCP"
             set_font(p.font, 12, True, RGBColor(100, 100, 100))
             val = float(re.findall(r"(\d+\.\d+)", evidence)[0]) if re.findall(r"(\d+\.\d+)", evidence) else 2.0
             draw_cwv_gauge(slide, "FCP", val, (1.8, 3.0))
             
        elif "3xx" in issue_id:
             p.text = "Redirect Flow:"
             set_font(p.font, 12, True, RGBColor(100, 100, 100))
             
             parts = evidence.split(' -> ')
             if len(parts) > 1:
                 x = 7.2
                 display_parts = parts[:3]
                 if len(parts) > 3: display_parts[-1] = "Final"

                 for i, part in enumerate(display_parts):
                     box_w = 2.0 if len(part) > 20 else 1.5
                     b = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(4.5), Inches(box_w), Inches(0.6))
                     b.fill.solid()
                     b.fill.fore_color.rgb = RGBColor(240, 240, 240) if i < len(display_parts)-1 else RGBColor(220, 255, 220)
                     b.text_frame.text = part
                     b.text_frame.paragraphs[0].font.size = Pt(9)
                     b.text_frame.paragraphs[0].font.color.rgb = RGBColor(0,0,0)
                     
                     if i < len(display_parts) - 1:
                         ar = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x+box_w), Inches(4.7), Inches(0.3), Inches(0.2))
                         ar.fill.solid()
                         ar.fill.fore_color.rgb = RGBColor(100, 100, 100)
                         x += (box_w + 0.3)
             
        else:
             p.text = txt["serp_sim_title"]
             set_font(p.font, 12, True, RGBColor(100, 100, 100))
             tf = box.text_frame
             tf.margin_left = Inches(0.2)
             tf.margin_top = Inches(0.2)
             p_serp = tf.add_paragraph()
             p_serp.text = f"{urlparse(url).netloc} › ..."
             set_font(p_serp.font, 12, False, RGBColor(32, 33, 36))
             
             if "short_desc" in issue_id or "missing_desc" in issue_id:
                 p_serp = tf.add_paragraph()
                 p_serp.space_before = Pt(5)
                 p_serp.text = evidence[:60] + "..." if evidence else "Title of the page"
                 set_font(p_serp.font, 18, False, RGBColor(26, 13, 171))
                 
                 p_serp = tf.add_paragraph()
                 p_serp.space_before = Pt(3)
                 if "missing" in issue_id:
                    p_serp.text = "No description available in code..."
                 else:
                    p_serp.text = evidence 
                 set_font(p_serp.font, 14, False, RGBColor(77, 81, 86))
             
             elif "long_title" in issue_id:
                 p_serp = tf.add_paragraph()
                 p_serp.space_before = Pt(5)
                 p_serp.text = evidence[:55] + " ..."
                 set_font(p_serp.font, 18, False, RGBColor(26, 13, 171))

                 p_serp = tf.add_paragraph()
                 p_serp.space_before = Pt(3)
                 p_serp.text = "The meta description of the page would appear here..."
                 set_font(p_serp.font, 14, False, RGBColor(77, 81, 86))

             else:
                 p_serp = tf.add_paragraph()
                 p_serp.space_before = Pt(5)
                 p_serp.text = evidence if evidence else "Untitled Page"
                 set_font(p_serp.font, 18, False, RGBColor(26, 13, 171)) 

    def draw_code_preview(slide):
        box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(7), Inches(4), Inches(5.8), Inches(1.5))
        box.fill.solid() # Fix
        box.fill.fore_color.rgb = RGBColor(245, 245, 245)
        box.line.color.rgb = RGBColor(200, 200, 200)
        tf = box.text_frame
        tf.margin_left = Inches(0.1)
        p = tf.add_paragraph()
        p.text = '<a href="javascript:void(0)">\n  Click Here\n</a>'
        set_font(p.font, 14, True, RGBColor(200, 0, 0)) # Red code
        
        label = slide.shapes.add_textbox(Inches(7), Inches(3.6), Inches(4), Inches(0.3))
        p = label.text_frame.add_paragraph()
        p.text = txt["code_sim_title"]
        set_font(p.font, 12, True, RGBColor(100, 100, 100))

    def draw_hreflang_preview(slide, url, missing_type):
        box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(7), Inches(4), Inches(5.8), Inches(2.0))
        box.fill.solid()
        box.fill.fore_color.rgb = RGBColor(245, 245, 245)
        box.line.color.rgb = RGBColor(200, 200, 200)
        
        tf = box.text_frame
        tf.margin_left = Inches(0.2)
        tf.margin_top = Inches(0.2)
        
        p = tf.add_paragraph()
        p.text = "<!-- Correct Implementation -->"
        set_font(p.font, 10, False, RGBColor(128, 128, 128))
        
        p = tf.add_paragraph()
        clean_url = url.split('?')[0][:40] + "..."
        if "default" in missing_type:
             p.text = f'<link rel="alternate" hreflang="x-default" href="{clean_url}" />'
             set_font(p.font, 11, True, RGBColor(200, 0, 0)) # Red highlight
        else:
             p.text = f'<link rel="alternate" hreflang="en" href="{clean_url}" />\n<link rel="alternate" hreflang="fr" href="..." />'
             set_font(p.font, 11, False, RGBColor(0, 0, 128))

        label = slide.shapes.add_textbox(Inches(7), Inches(3.6), Inches(4), Inches(0.3))
        p = label.text_frame.add_paragraph()
        p.text = txt["code_sim_title"]
        set_font(p.font, 12, True, RGBColor(100, 100, 100))

    def draw_rich_snippet_preview(slide, url):
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(7), Inches(4), Inches(5.8), Inches(2.0)) # Moved down
        box.fill.solid() # Fix
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
        p.text = "★★★★★ Rating: 4.8 · $199.00 · In stock"
        set_font(p.font, 12, False, RGBColor(231, 113, 27))
        p = tf.add_paragraph()
        p.space_before = Pt(3)
        p.text = "This is a rich result enabled by Schema..."
        set_font(p.font, 14, False, RGBColor(77, 81, 86))
        label = slide.shapes.add_textbox(Inches(7), Inches(3.6), Inches(4), Inches(0.3))
        p = label.text_frame.add_paragraph()
        p.text = txt["rich_sim_title"]
        set_font(p.font, 12, True, RGBColor(100, 100, 100))

    # Cover
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.shapes.add_shape(1, 0, 0, Inches(13.333), Inches(7.5))
    bg.fill.solid() # Fix
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
    for s in slides_data:
        t_data = get_translated_text(s['id'], lang, s.get('args'))
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        
        # Header
        h_shape = slide.shapes.add_shape(1, 0, 0, Inches(13.333), Inches(1.2))
        h_shape.fill.solid()
        h_shape.fill.fore_color.rgb = RGBColor(240, 242, 246)
        h_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(10), Inches(0.8))
        p = h_box.text_frame.add_paragraph()
        p.text = t_data['title']
        set_font(p.font, 32, True, RGBColor(50, 50, 50))
        
        sev_color = RGBColor(220, 53, 69) if s['severity'] == "Critical" else RGBColor(253, 126, 20)
        sev_box = slide.shapes.add_textbox(Inches(11), Inches(0.35), Inches(2), Inches(0.5))
        p = sev_box.text_frame.add_paragraph()
        p.text = s['severity']
        p.alignment = PP_ALIGN.CENTER
        set_font(p.font, 18, True, sev_color)
        
        # Category
        cat_key = f"cat_{s['category']}"
        cat_label = txt.get(cat_key, s['category'].upper())
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
        p.text = t_data['desc']
        set_font(p.font, 14, False, RGBColor(80, 80, 80))
        
        # Impact
        i_title = slide.shapes.add_textbox(Inches(0.5), Inches(3.6), Inches(6), Inches(0.5))
        p = i_title.text_frame.add_paragraph()
        p.text = txt["ppt_business_impact"]
        set_font(p.font, 18, True, RGBColor(30, 30, 30))
        i_box = slide.shapes.add_textbox(Inches(0.5), Inches(4.1), Inches(6), Inches(1.2))
        tf = i_box.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
        p = tf.add_paragraph()
        p.text = t_data['impact']
        set_font(p.font, 14, False, RGBColor(220, 53, 69))

        # Suggestion (Fixed Layout: Absolute Bottom)
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
        p.text = t_data['suggestion']
        set_font(p.font, 14, False, RGBColor(21, 87, 36))

        # Right Column Split (URL List)
        ex_title = slide.shapes.add_textbox(Inches(7), Inches(1.5), Inches(5.8), Inches(0.5))
        p = ex_title.text_frame.add_paragraph()
        p.text = txt["ppt_slide_ex_title"]
        set_font(p.font, 18, True, RGBColor(30, 30, 30))
        
        ex_box = slide.shapes.add_textbox(Inches(7), Inches(2.0), Inches(5.8), Inches(1.5)) 
        tf = ex_box.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
        
        for idx, url in enumerate(s['examples'][:4]): 
            p = tf.add_paragraph()
            # Visualize Duplicate Logic
            if s['id'] == 'duplicate' and "Duplicate Group:" in url:
                 parts = url.split("\n")
                 p.text = f"Group {idx+1}:\n   • {parts[1].replace('- ', '').strip()}\n   • {parts[2].replace('- ', '').strip()}"
                 set_font(p.font, 10, False, RGBColor(80, 80, 80))
            else:
                 p.text = f"• {url}"
                 set_font(p.font, 11, False, RGBColor(0, 102, 204))
            
            p.space_after = Pt(6)

        # Visualization (Visual Area)
        is_serp = any(k in s['id'] for k in ["title", "desc", "favicon", "alt", "lcp", "inp", "cls", "3xx", "fcp"])
        is_rich = "jsonld" in s['id']
        is_code = "js_links" in s['id'] or "anchor" in s['id']
        is_hreflang = "hreflang" in s['id']
        is_cwv = any(k in s['id'] for k in ["lcp", "inp", "cls", "fcp", "risk"])
        is_img = "alt" in s['id'] or "favicon" in s['id']
        is_3xx = "3xx" in s['id'] 
        
        ev = s.get('example_evidence', '')
        ex_url = s['examples'][0] if s['examples'] else "example.com"
        # Cleaning URL for display
        if "Duplicate" in ex_url: ex_url = ex_url.split("\n")[1].replace("- ", "").strip()
        if "3xx" in s['id'] and s.get('args'): ev = s['args'][0]

        if is_code:
            draw_code_preview(slide)
        elif is_hreflang:
            type_str = s['id']
            if "invalid" in type_str and s.get('args'):
                type_str = f"invalid: {s['args'][0]}"
            draw_hreflang_preview(slide, ex_url, type_str)
        elif is_rich:
            draw_rich_snippet_preview(slide, ex_url)
        elif is_serp:
            draw_serp_preview(slide, s['id'], t_data['title'], ev, ex_url)

    out = BytesIO()
    prs.save(out)
    out.seek(0)
    return out

# --- 7. UI Logic ---
# 初始化 Session State
if 'audit_data' not in st.session_state: st.session_state['audit_data'] = None
if 'audit_issues' not in st.session_state: st.session_state['audit_issues'] = []
if 'language' not in st.session_state: st.session_state['language'] = "zh"
if 'cwv_data' not in st.session_state: st.session_state['cwv_data'] = None
if 'sitemap_hreflang_found' not in st.session_state: st.session_state['sitemap_hreflang_found'] = False

lang = st.session_state['language']
ui = TRANSLATIONS[lang]

with st.sidebar:
    st.title(ui["sidebar_title"])
    st.caption(ui["sidebar_caption"])
    st.divider()
    
    sl = st.radio(ui["lang_label"], ["中文", "English"], index=0 if lang=="zh" else 1)
    if (sl == "中文" and lang == "en") or (sl == "English" and lang == "zh"):
        st.session_state['language'] = "zh" if sl == "中文" else "en"
        st.rerun()

    st.divider()
    opts = ui["nav_options"]
    keys = ["input", "dashboard", "matrix", "ppt"]
    sel = st.radio(ui["nav_label"], opts)
    menu_key = keys[opts.index(sel)]
    
    st.divider()
    if st.session_state['audit_data']:
        st.success(ui["cache_info"].format(len(st.session_state['audit_data'])))
        st.markdown(f"**{ui['sitemap_status_title']}**")
        if st.session_state['sitemap_hreflang_found']: st.caption(ui["sitemap_found_href"])
        else: st.caption(ui["sitemap_no_href"])
        
        if st.button(ui["clear_data"]):
            st.session_state['audit_data'] = None
            st.session_state['audit_issues'] = []
            st.session_state['cwv_data'] = None
            st.rerun()

if menu_key == "input":
    st.header(ui["input_header"])
    st.info(ui["input_info"])
    c1, c2 = st.columns([3, 1])
    with c1: target_url = st.text_input(ui["input_label"], placeholder=ui["input_placeholder"])
    with c2: max_pages = st.number_input(ui.get("max_pages_label", "Max Pages"), min_value=1, max_value=1000, value=100)
    
    with st.expander(ui.get("adv_settings", "Advanced")):
        allow_sub = st.checkbox(ui["allow_subdomains_label"], value=False)
        allow_out = st.checkbox(ui["allow_outside_folder_label"], value=False)
        check_robots_flag = st.checkbox(ui["check_robots_label"], value=True)
        crawl_sitemap_flag = st.checkbox(ui["crawl_sitemap_label"], value=True)
        baidu_mode_flag = st.checkbox(ui["baidu_mode_label"], value=False) # New
        manual_sitemaps_text = st.text_area(ui.get("manual_sitemaps", "Manual Sitemaps"), placeholder="https://example.com/sitemap.xml")
        manual_sitemaps = [s.strip() for s in manual_sitemaps_text.split('\n') if s.strip()]
    
    with st.expander(ui.get("psi_settings", "Google PSI")):
        psi_key = st.text_input(ui.get("psi_api_key_label", "API Key"), type="password", help=ui.get("psi_api_help", ""))
        psi_list_url = st.text_input(ui.get("psi_list_url_label", "List URL"))
        psi_detail_url = st.text_input(ui.get("psi_detail_url_label", "Detail URL"))
        st.caption(ui["psi_get_key"])

    if st.button(ui["start_btn"], type="primary"):
        if not target_url or not is_valid_url(target_url): 
            st.error(ui["error_url"])
        else:
            with st.spinner(ui["spinner_crawl"].format(max_pages)):
                data, issues, error_msg = crawl_website(
                    target_url, max_pages, lang, None, manual_sitemaps, psi_key, 
                    psi_list_url, psi_detail_url, check_robots_flag, crawl_sitemap_flag,
                    allow_sub, allow_out, baidu_mode_flag
                )
                if not data:
                    st.error(ui["error_no_data"].format(error_msg or "Unknown Error"))
                else:
                    st.session_state['audit_data'] = data
                    st.session_state['audit_issues'] = issues
                    st.success(ui["success_audit"].format(len(data)))
                    st.balloons()

elif menu_key == "dashboard":
    st.header(ui["dashboard_header"])
    if not st.session_state['audit_data']: st.warning(ui["warn_no_data"])
    else:
        if st.session_state.get('cwv_data'):
            c = st.session_state['cwv_data']
            st.subheader(ui["cwv_title"])
            st.caption(ui["cwv_source"])
            c1, c2, c3, c4 = st.columns(4)
            def metric_color(val, good, poor):
                if val <= good: return "normal"
                if val >= poor: return "inverse"
                return "off"
            c1.metric("LCP (Loading)", f"{c['LCP']:.2f}s", delta_color=metric_color(c['LCP'], 2.5, 4.0))
            c2.metric("CLS (Visual)", f"{c['CLS']:.3f}", delta_color=metric_color(c['CLS'], 0.1, 0.25))
            c3.metric("INP (Interact)", f"{c['INP']}ms", delta_color=metric_color(c['INP'], 200, 500))
            c4.metric("FCP", f"{c['FCP']:.2f}s")
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
            if issues:
                issue_counts = pd.DataFrame(issues)['id'].value_counts().reset_index()
                issue_counts.columns = ['id', 'count']
                issue_counts['name'] = issue_counts['id'].apply(lambda x: get_translated_text(x, lang)['title'])
                st.bar_chart(issue_counts.set_index('name'))
            else: st.info(ui["chart_no_issues"])
        with c2:
            st.subheader(ui["chart_status"])
            if not df.empty: st.bar_chart(df['Status'].value_counts())

elif menu_key == "matrix":
    st.header(ui["matrix_header"])
    if not st.session_state['audit_data']: st.warning(ui["warn_no_data"])
    else:
        df = pd.DataFrame(st.session_state['audit_data'])
        st.dataframe(df, use_container_width=True)
        st.download_button(ui["download_csv"], df.to_csv().encode('utf-8'), "audit.csv")

elif menu_key == "ppt":
    st.header(ui["ppt_header"])
    if not st.session_state['audit_issues']: st.warning(ui["warn_no_data"])
    else:
        raw = st.session_state['audit_issues']
        grouped = {}
        for i in raw:
            iid = i['id']
            if iid not in grouped:
                grouped[iid] = {
                    "id": iid, "category": i['category'], "severity": i['severity'],
                    "count": 0, "examples": [], "args": i.get('args', []),
                    "example_evidence": i.get("evidence", "")
                }
            grouped[iid]['count'] += 1
            if len(grouped[iid]['examples']) < 5:
                if iid == "duplicate" and "meta" in i:
                     # Clean grouping for duplicate
                     grouped[iid]['examples'].append(f"Duplicate Group:\n- {i['url']}\n- {i['meta']}")
                else:
                     grouped[iid]['examples'].append(i['url'])
        
        slides = sorted(list(grouped.values()), key=lambda x: (
            CATEGORY_ORDER.index(x['category']),
            get_issue_priority(x['id']),
            SEVERITY_ORDER.get(x['severity'], 3)
        ))
        
        st.write(f"### {ui['ppt_download_header']}")
        st.info(ui["ppt_info"])
        if st.button(ui["ppt_btn"]):
            with st.spinner("Generating..."):
                f = create_styled_pptx(slides, lang)
                st.download_button(ui["ppt_btn"], f, f"seo_audit_{lang}.pptx")
        
        if 'slide_index' not in st.session_state: st.session_state.slide_index = 0
        if st.session_state.slide_index >= len(slides): st.session_state.slide_index = 0
        
        s = slides[st.session_state.slide_index]
        t_data = get_translated_text(s['id'], lang, s['args'])
        
        with st.container(border=True):
            st.caption(f"📂 {ui.get('cat_'+s['category'], s['category'])}")
            st.markdown(f"### {ui['ppt_slide_title']} {t_data['title']}")
            
            c1, c2 = st.columns([1, 1])
            with c1:
                color = "red" if s['severity'] == "Critical" else "orange"
                st.markdown(f"**{ui['ppt_severity']}** :{color}[{s['severity']}]")
                st.markdown(f"**{ui['ppt_impact']}** {ui['ppt_impact_desc'].format(s['count'])}")
                
                st.markdown(f"**{ui['ppt_desc']}**")
                st.write(t_data['desc'])
                
                st.markdown(f"**{ui['ppt_business_impact']}**") 
                st.error(t_data['impact']) 
                
                st.info(f"{ui['ppt_sugg']} {t_data['suggestion']}")
            with c2:
                # Visualization Logic
                is_serp = any(k in s['id'] for k in ["title", "desc", "favicon", "alt", "lcp", "inp", "cls", "3xx", "fcp"])
                is_rich = "jsonld" in s['id']
                is_code = "js_links" in s['id'] or "anchor" in s['id']
                is_hreflang = "hreflang" in s['id']
                is_cwv = any(k in s['id'] for k in ["lcp", "inp", "cls", "fcp", "risk"])
                is_img = "alt" in s['id'] or "favicon" in s['id']
                is_3xx = "3xx" in s['id'] 
                
                ev = s.get('example_evidence', '')
                ex_url = s['examples'][0] if s['examples'] else "example.com"
                # Cleaning URL for display
                if "Duplicate" in ex_url: ex_url = ex_url.split("\n")[1].replace("- ", "").strip()
                if "3xx" in s['id'] and s.get('args'): ev = s['args'][0]

                if is_code:
                    draw_code_preview(slide)
                elif is_hreflang:
                    type_str = s['id']
                    if "invalid" in type_str and s.get('args'):
                        type_str = f"invalid: {s['args'][0]}"
                    draw_hreflang_preview(slide, ex_url, type_str)
                elif is_rich:
                    draw_rich_snippet_preview(slide, ex_url)
                elif is_serp:
                    draw_serp_preview(slide, s['id'], t_data['title'], ev, ex_url)

    out = BytesIO()
    prs.save(out)
    out.seek(0)
    return out
