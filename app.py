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

# --- 2. 排序逻辑配置 (Strict Logic Flow) ---
# 顺序：访问 -> 索引 -> 技术 -> 内容 -> 体验 -> 性能(CWV压轴)
CATEGORY_ORDER = ["access", "indexability", "technical", "content", "image_ux", "cwv_performance"]
SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}

# 问题优先级列表 (用于同类问题排序)
ISSUE_PRIORITY_LIST = [
    # 1. Access
    "no_robots", "robots_bad_rule", "robots_no_sitemap", "no_sitemap", "sitemap_invalid",
    "http_5xx", "http_4xx", "soft_404", "http_3xx",
    
    # 2. Indexability
    "duplicate", "missing_canonical", "hreflang_invalid", "hreflang_no_default", "missing_hreflang",
    
    # 3. Technical
    "missing_viewport", "missing_jsonld", "js_links", "url_underscore", "url_uppercase",
    
    # 4. Content
    "missing_title", "short_title", "long_title",
    "missing_desc", "short_desc",
    "missing_h1",
    
    # 5. UX & Assets
    "no_favicon", "missing_alt", "alt_bad_quality", "anchor_bad_quality", "cls_risk",
    
    # 6. CWV Performance
    "lcp_issue", "inp_issue", "cls_issue"
]

def get_issue_priority(issue_id):
    try:
        return ISSUE_PRIORITY_LIST.index(issue_id)
    except ValueError:
        return 999 

# --- 3. 国际化字典 (i18n) ---
TRANSLATIONS = {
    "zh": {
        "sidebar_title": "🔍 AuditAI Pro",
        "sidebar_caption": "旗舰审计版 v4.9",
        "nav_label": "功能导航",
        "nav_options": ["输入网址", "仪表盘", "数据矩阵", "PPT 生成器"],
        "lang_label": "语言 / Language",
        "clear_data": "清除数据并重置",
        "cache_info": "已缓存 {} 个页面",
        "sitemap_status_title": "Sitemap 状态:",
        "sitemap_found_href": "✅ 发现 Hreflang 配置", 
        "sitemap_no_href": "⚠️ 未发现 Hreflang",     
        "sitemap_missing": "❌ 未找到 Sitemap",

        "psi_settings": "Google PSI API 设置 (可选)",
        "psi_api_key_label": "输入 Google PageSpeed API Key",
        "psi_api_help": "建议填入以获取 LCP/CLS/INP 真实数据。留空则只进行代码审计。",
        "psi_get_key": "没有 API Key? [点击这里免费申请](https://developers.google.com/speed/docs/insights/v5/get-started)",
        "psi_fetching": "正在调用 Google API 获取首页真实 CWV 数据...",
        "psi_success": "成功获取真实用户数据！",
        "psi_error": "API 调用失败或无 CrUX 数据",
        
        "input_header": "开始深度审计",
        "input_info": "说明: v4.9 严格遵循审计逻辑 (Access->Index->Tech->Content->UX->CWV)，修复了中英文案混杂问题。",
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
        "ppt_info": "说明：生成的 PPT 已优化为 16:9 宽屏，包含重复内容溯源及可视化预览。",
        "ppt_btn": "生成并下载美化版 .pptx",
        "ppt_preview_header": "网页版预览",
        "ppt_slide_title": "问题类型:",
        "ppt_category": "分类:",
        "ppt_severity": "严重程度:",
        "ppt_impact": "影响范围:",
        "ppt_impact_desc": "在已爬取样本中发现 **{}** 个页面。",
        "ppt_desc": "🔴 问题描述:",
        "ppt_business_impact": "📉 商业与 SEO 影响:", 
        "ppt_sugg": "✅ 修复建议:",
        "ppt_examples": "🔍 受影响页面示例:",
        "ppt_prev": "⬅️ 上一页",
        "ppt_next": "下一页 ➡️",
        
        # Categories Labels
        "cat_access": "1. 可访问性与索引 (Access & Indexing)",
        "cat_indexability": "2. 索引规范性 (Indexability)",
        "cat_technical": "3. 技术与架构 (Technical SEO)",
        "cat_content": "4. 页面内容 (On-Page Content)",
        "cat_image_ux": "5. 用户体验与资源 (UX & Assets)",
        "cat_cwv_performance": "6. 核心性能指标 (Core Web Vitals)",

        "ppt_cover_title": "SEO 深度技术审计报告",
        "ppt_cover_sub": "Generated by AuditAI Pro v4.9",
        "ppt_slide_desc_title": "深度分析",
        "ppt_slide_count_title": "样本中受影响页面数: {} 个",
        "ppt_slide_ex_title": "受影响页面示例", 
        "ppt_slide_sugg_title": "💡 修复建议:",
        "serp_sim_title": "Google 搜索结果模拟 (SERP):",
        "rich_sim_title": "富媒体结果模拟 (Rich Results):",

        # Issues
        "lcp_issue": "LCP (最大内容绘制) 超标", "lcp_desc": "LCP 为 {:.2f}s (目标 <2.5s)。加载过慢。", "lcp_impact": "核心排名因素。高跳出率。", "lcp_sugg": "优化图片大小 (WebP)，使用 CDN，推迟非关键 JS，预加载 LCP 元素。",
        "cls_issue": "CLS (累积布局偏移) 超标", "cls_desc": "CLS 为 {:.3f} (目标 <0.1)。视觉不稳定。", "cls_impact": "核心排名因素。用户体验差。", "cls_sugg": "指定图片宽高，避免动态内容。",
        "inp_issue": "INP (交互延迟) 超标", "inp_desc": "INP 为 {}ms (目标 <200ms)。响应迟钝。", "inp_impact": "核心排名因素。影响转化。", "inp_sugg": "优化 JS 执行，减少主线程阻塞。",
        
        "no_robots": "缺失 Robots.txt", "no_robots_desc": "无法访问 robots.txt。", "no_robots_impact": "爬取不可控，浪费预算。", "no_robots_sugg": "创建文件。",
        "robots_bad_rule": "Robots.txt 封禁风险", "robots_desc": "检测到全站封禁规则。", "robots_impact": "导致不收录。", "robots_bad_rule_sugg": "移除 Disallow: / 规则。",
        "robots_no_sitemap": "Robots 未声明 Sitemap", "robots_no_sitemap_desc": "未指明 Sitemap 位置。", "robots_no_sitemap_impact": "发现页面变慢。", "robots_no_sitemap_sugg": "添加 Sitemap 指令。",
        "no_sitemap": "Sitemap 访问失败", "no_sitemap_desc": "无法访问 Sitemap。", "no_sitemap_impact": "深层页面难发现。", "no_sitemap_sugg": "检查 Sitemap URL。",
        "sitemap_invalid": "Sitemap 格式错误", "sitemap_invalid_desc": "XML 解析失败。", "sitemap_invalid_impact": "Sitemap 失效。", "sitemap_invalid_sugg": "修复 XML 语法。",
        "no_favicon": "缺失 Favicon", "no_favicon_desc": "首页无图标。", "no_favicon_impact": "降低 SERP 点击率。", "no_favicon_sugg": "配置 favicon。",
        
        "duplicate": "发现未规范化的重复内容", "duplicate_desc": "内容高度重复且 Canonical 未统一。", "duplicate_impact": "权重分散，关键词竞争。", "duplicate_sugg": "使用 Canonical 指向原件。",
        
        "3xx_title": "内部链接重定向 (3xx)", "3xx_desc": "链接发生跳转。", "3xx_impact": "浪费爬取预算。", "3xx_sugg": "更新链接直接指向目标。",
        "4xx_title": "死链 (4xx)", "4xx_desc": "链接返回 404。", "4xx_impact": "破坏体验，权重流失。", "4xx_sugg": "修复死链。",
        "5xx_title": "服务器错误 (5xx)", "5xx_desc": "服务器报错。", "5xx_impact": "严重影响收录。", "5xx_sugg": "检查服务器日志。",
        
        "hreflang_invalid": "Hreflang 格式错误", "hreflang_invalid_desc": "代码不符合 ISO 标准。", "hreflang_invalid_impact": "国际化失效。", "hreflang_invalid_sugg": "使用标准 ISO 代码 (如 en-US)。",
        "hreflang_no_default": "Hreflang 缺失 x-default", "hreflang_no_default_desc": "无默认回退。", "hreflang_no_default_impact": "语言匹配错误。", "hreflang_no_default_sugg": "添加 x-default 标记。",
        
        "alt_bad_quality": "图片 Alt 质量差", "alt_bad_quality_desc": "使用无意义词汇。", "alt_bad_quality_impact": "错失图片流量。", "alt_bad_quality_sugg": "使用描述性关键词。",
        "anchor_bad_quality": "锚文本质量差", "anchor_bad_quality_desc": "使用通用词汇。", "anchor_bad_quality_impact": "无法传递相关性。", "anchor_bad_quality_sugg": "使用描述性锚文本。",
        
        "cls_risk": "CLS 布局偏移风险 (静态)", "cls_risk_desc": "Img 缺失宽高属性。", "cls_risk_impact": "导致页面抖动。", "cls_risk_sugg": "为图片指定 width 和 height。",
        
        "missing_title": "缺失 Title", "missing_title_desc": "无标题标签。", "missing_title_impact": "严重影响排名。", "missing_title_sugg": "添加标题。",
        "short_title": "标题过短", "short_title_desc": "标题太短。", "short_title_impact": "覆盖词少。", "short_title_sugg": "扩充标题。",
        "long_title": "标题过长", "long_title_desc": "标题 >60 字符。", "long_title_impact": "SERP 截断。", "long_title_sugg": "精简标题长度。",
        
        "missing_desc": "缺失 Meta Description", "missing_desc_desc": "无描述。", "missing_desc_impact": "降低点击率。", "missing_desc_sugg": "添加描述。",
        "short_desc": "Meta Description 过短", "short_desc_desc": "内容太少。", "short_desc_impact": "吸引力不足。", "short_desc_sugg": "扩充描述。",
        
        "missing_h1": "缺失 H1", "missing_h1_desc": "无 H1。", "missing_h1_impact": "结构不清。", "missing_h1_sugg": "添加 H1。",
        
        "missing_viewport": "缺失 Viewport", "missing_viewport_desc": "无移动端配置。", "missing_viewport_impact": "移动端排名下降。", "missing_viewport_sugg": "添加 Viewport 标签。",
        
        "missing_canonical": "缺失 Canonical", "missing_canonical_desc": "无规范标签。", "missing_canonical_impact": "重复内容风险。", "missing_canonical_sugg": "添加 Canonical 标签。",
        
        "missing_jsonld": "缺失结构化数据", "missing_jsonld_desc": "未检测到 Schema 标记。", "missing_jsonld_impact": "无富媒体结果。", 
        "missing_jsonld_sugg": "根据页面类型添加 JSON-LD：\n- 产品页: Product\n- 文章页: Article\n- 首页: Organization",
        
        "missing_hreflang": "缺失 Hreflang", "missing_hreflang_desc": "无语言标记。", "missing_hreflang_impact": "国际化差。", "missing_hreflang_sugg": "添加 Hreflang 标签。",
        
        "soft_404": "疑似软 404", "soft_404_desc": "假 200 页面。", "soft_404_impact": "浪费预算。", "soft_404_sugg": "配置 404 状态码。",
        
        "missing_alt": "缺失 Alt", "missing_alt_desc": "图片无 Alt。", "missing_alt_impact": "不利图片 SEO。", "missing_alt_sugg": "添加 Alt 属性。",
        
        "js_links": "JS 伪链接", "js_links_desc": "href=javascript。", "js_links_impact": "爬虫无法抓取。", "js_links_sugg": "使用标准链接。",
        
        "url_underscore": "URL 含下划线", "url_underscore_desc": "使用 _。", "url_underscore_impact": "分词困难。", "url_underscore_sugg": "使用连字符 -。",
        "url_uppercase": "URL 含大写", "url_uppercase_desc": "混用大小写。", "url_uppercase_impact": "重复收录风险。", "url_uppercase_sugg": "转小写。"
    },
    "en": {
        "sidebar_title": "🔍 AuditAI Pro",
        "sidebar_caption": "Deep Audit Edition v4.9",
        "nav_label": "Navigation",
        "nav_options": ["Input URL", "Dashboard", "Data Matrix", "PPT Generator"],
        "lang_label": "Language / 语言",
        "clear_data": "Clear Data & Reset",
        "cache_info": "Cached {} pages",
        "sitemap_status_title": "Sitemap Status:",
        "sitemap_found_href": "✅ Hreflang Found", 
        "sitemap_no_href": "⚠️ No Hreflang",       
        "sitemap_missing": "❌ Sitemap Missing",
        
        "psi_settings": "Google PSI API Settings (Optional)",
        "psi_api_key_label": "Enter Google PageSpeed API Key",
        "psi_api_help": "Leave empty for static check only.",
        "psi_get_key": "No API Key? [Get one for free here](https://developers.google.com/speed/docs/insights/v5/get-started)",
        "psi_fetching": "Fetching real CWV data...",
        "psi_success": "Real user data fetched!",
        "psi_error": "API Failed or No CrUX Data",
        
        "input_header": "Start Deep Audit",
        "input_info": "Note: v4.9 features strict logical ordering (Access -> Tech -> Content -> UX -> CWV).",
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
        "ppt_business_impact": "📉 Business & SEO Impact:",
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
        "cat_cwv_performance": "6. Core Web Vitals (Performance)",
        
        "ppt_cover_title": "SEO Technical Audit",
        "ppt_cover_sub": "Generated by AuditAI Pro v4.9",
        "ppt_slide_desc_title": "Description & Impact",
        "ppt_slide_count_title": "Affected Pages (in sample): {}",
        "ppt_slide_ex_title": "Affected Page Examples",
        "ppt_slide_sugg_title": "💡 Recommendation:",
        "serp_sim_title": "Google SERP Simulation:",
        "rich_sim_title": "Rich Results Simulation:",

        # Issues (Full sentences)
        "lcp_issue": "LCP Fails", "lcp_desc": "LCP is {:.2f}s (Target <2.5s). Main content loads too slowly.", "lcp_impact": "Core Ranking Factor. High bounce rates.", "lcp_sugg": "Optimize images, use CDN, defer JS.",
        "cls_issue": "CLS Fails", "cls_desc": "CLS is {:.3f} (Target <0.1). Layout shifts detected.", "cls_impact": "Ranking Factor. Bad user experience.", "cls_sugg": "Set width/height for media.",
        "inp_issue": "INP Fails", "inp_desc": "INP is {}ms (Target <200ms). Slow interactivity.", "inp_impact": "Ranking Factor. Low conversion rates.", "inp_sugg": "Optimize JS execution.",
        
        "no_robots": "Missing Robots.txt", "no_robots_desc": "Robots.txt not found.", "no_robots_impact": "Crawling cannot be controlled.", "no_robots_sugg": "Create robots.txt.",
        "robots_bad_rule": "Robots Blocking", "robots_desc": "Global disallow rule found.", "robots_impact": "Site will be de-indexed.", "robots_bad_rule_sugg": "Remove Disallow: /.",
        "robots_no_sitemap": "Sitemap Missing in Robots", "robots_no_sitemap_desc": "Sitemap link missing.", "robots_no_sitemap_impact": "Slow content discovery.", "robots_no_sitemap_sugg": "Add Sitemap directive.",
        "no_sitemap": "Sitemap Failed", "no_sitemap_desc": "Access denied.", "no_sitemap_impact": "Poor indexing coverage.", "no_sitemap_sugg": "Check Sitemap URL.",
        "sitemap_invalid": "Invalid Sitemap", "sitemap_invalid_desc": "XML syntax error.", "sitemap_invalid_impact": "Unreadable sitemap.", "sitemap_invalid_sugg": "Validate XML.",
        "no_favicon": "Missing Favicon", "no_favicon_desc": "No icon on homepage.", "no_favicon_impact": "Lower CTR in SERPs.", "no_favicon_sugg": "Add favicon tag.",
        
        "duplicate": "Duplicate Content", 
        "duplicate_desc": "Duplicate found without canonical.", 
        "duplicate_impact": "Keyword cannibalization & diluted equity.", 
        "duplicate_sugg": "Use canonical tags.",
        
        "3xx_title": "Redirect Chain", "3xx_desc": "Internal link redirects.", "3xx_impact": "Wasted budget & latency.", "3xx_sugg": "Update links directly.",
        "4xx_title": "Broken Link", "4xx_desc": "Link returns 4xx error.", "4xx_impact": "Bad UX & equity loss.", "4xx_sugg": "Fix broken links.",
        "5xx_title": "Server Error", "5xx_desc": "Link returns 5xx error.", "5xx_impact": "Google reduces crawl rate.", "5xx_sugg": "Check server logs.",
        
        "hreflang_invalid": "Invalid Hreflang", "hreflang_invalid_desc": "Invalid ISO code.", "hreflang_invalid_impact": "Targeting fails.", "hreflang_invalid_sugg": "Use standard codes.",
        "hreflang_no_default": "No x-default", "hreflang_no_default_desc": "Missing fallback.", "hreflang_no_default_impact": "Wrong lang shown.", "hreflang_no_default_sugg": "Add x-default.",
        
        "alt_bad_quality": "Bad Alt Text", "alt_bad_quality_desc": "Generic text used.", "alt_bad_quality_impact": "No image SEO value.", "alt_bad_quality_sugg": "Use descriptive text.",
        "anchor_bad_quality": "Bad Anchor", "anchor_bad_quality_desc": "Generic anchor text.", "anchor_bad_quality_impact": "No context passed.", "anchor_bad_quality_sugg": "Use keywords.",
        
        "cls_risk": "CLS Risk (Static)", "cls_risk_desc": "Missing dimensions.", "cls_risk_impact": "Layout shifts.", "cls_risk_sugg": "Add width/height.",
        
        "missing_title": "Missing Title", "missing_title_desc": "No title tag.", "missing_title_impact": "Ranking loss.", "missing_title_sugg": "Add title.",
        "short_title": "Title Short", "short_title_desc": "Too short.", "short_title_impact": "Missed keywords.", "short_title_sugg": "Expand title.",
        "long_title": "Title Long", "long_title_desc": "Too long.", "long_title_impact": "Truncated.", "long_title_sugg": "Shorten title.",
        
        "missing_desc": "Missing Desc", "missing_desc_desc": "No meta desc.", "missing_desc_impact": "Lower CTR.", "missing_desc_sugg": "Add description.",
        "short_desc": "Desc Short", "short_desc_desc": "Too thin.", "short_desc_impact": "Low appeal.", "short_desc_sugg": "Expand description.",
        
        "missing_h1": "Missing H1", "missing_h1_desc": "No H1.", "missing_h1_impact": "Poor structure.", "missing_h1_sugg": "Add H1.",
        
        "missing_viewport": "No Viewport", "missing_viewport_desc": "Not mobile friendly.", "missing_viewport_impact": "Ranking drop.", "missing_viewport_sugg": "Add viewport.",
        
        "missing_canonical": "No Canonical", "missing_canonical_desc": "Missing tag.", "missing_canonical_impact": "Duplicate risk.", "missing_canonical_sugg": "Add canonical.",
        
        "missing_jsonld": "No Schema", "missing_jsonld_desc": "No JSON-LD.", "missing_jsonld_impact": "No rich results.", 
        "missing_jsonld_sugg": "Add JSON-LD for page type.",
        
        "missing_hreflang": "No Hreflang", "missing_hreflang_desc": "Missing tags.", "missing_hreflang_impact": "Poor geo-targeting.", "missing_hreflang_sugg": "Add hreflang.",
        
        "soft_404": "Soft 404", "soft_404_desc": "Fake 200.", "soft_404_impact": "Wasted budget.", "soft_404_sugg": "Use 404.",
        
        "missing_alt": "Missing Alt", "missing_alt_desc": "No alt text.", "missing_alt_impact": "Bad image SEO.", "missing_alt_sugg": "Add alt attributes.",
        
        "js_links": "JS Links", "js_links_desc": "Uncrawlable.", "js_links_impact": "Broken graph.", "js_links_sugg": "Use standard links.",
        
        "url_underscore": "URL Underscores", "url_underscore_desc": "Has _.", "url_underscore_impact": "Bad parsing.", "url_underscore_sugg": "Use hyphens.",
        "url_uppercase": "URL Uppercase", "url_uppercase_desc": "Has Upper.", "url_uppercase_impact": "Duplicate risk.", "url_uppercase_sugg": "Lowercase."
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

# --- Analyze CWV Data for Issues ---
def check_cwv_issues(cwv_data, url, lang="zh"):
    issues = []
    if not cwv_data or "error" in cwv_data: return issues
    
    t = TRANSLATIONS[lang]
    # 使用统一的 category_key
    category_key = "cwv_performance"

    # LCP
    lcp = cwv_data.get("LCP", 0)
    if lcp > 2.5:
        severity = "Critical" if lcp > 4.0 else "High"
        issues.append({
            "id": "lcp_issue", "category": category_key, "severity": severity,
            "title": t["lcp_issue"], "desc": t["lcp_desc"].format(lcp), "impact": t["lcp_impact"], "suggestion": t["lcp_sugg"],
            "url": url, "examples": [url] 
        })
        
    # INP (Logic Order: LCP -> INP -> CLS)
    inp = cwv_data.get("INP", 0)
    if inp > 200:
        severity = "Critical" if inp > 500 else "High"
        issues.append({
            "id": "inp_issue", "category": category_key, "severity": severity,
            "title": t["inp_issue"], "desc": t["inp_desc"].format(inp), "impact": t["inp_impact"], "suggestion": t["inp_sugg"],
            "url": url, "examples": [url]
        })

    # CLS
    cls = cwv_data.get("CLS", 0)
    if cls > 0.1:
        severity = "Critical" if cls > 0.25 else "High"
        issues.append({
            "id": "cls_issue", "category": category_key, "severity": severity,
            "title": t["cls_issue"], "desc": t["cls_desc"].format(cls), "impact": t["cls_impact"], "suggestion": t["cls_sugg"],
            "url": url, "examples": [url]
        })
        
    return issues

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
            issues.append({"id": "no_robots", "category": "access", "severity": "Medium", "title": t["no_robots"], "desc": t["no_robots_desc"], "impact": t["no_robots_impact"], "suggestion": t["no_robots_sugg"], "url": robots_url, "examples": [robots_url]})
        else:
            content = r.text.lower()
            if "disallow: /" in content and "allow:" not in content:
                 issues.append({"id": "robots_bad_rule", "category": "access", "severity": "Critical", "title": t["robots_bad_rule"], "desc": t["robots_desc"], "impact": t["robots_impact"], "suggestion": t["robots_bad_rule_sugg"], "url": robots_url, "examples": [robots_url]})
            if "sitemap:" not in content:
                 issues.append({"id": "robots_no_sitemap", "category": "access", "severity": "Low", "title": t["robots_no_sitemap"], "desc": t["robots_no_sitemap_desc"], "impact": t["robots_no_sitemap_impact"], "suggestion": t["robots_no_sitemap_sugg"], "url": robots_url, "examples": [robots_url]})
        r.close()
    except: 
        issues.append({"id": "no_robots", "category": "access", "severity": "Medium", "title": t["no_robots"], "desc": "Connection failed.", "impact": t["no_robots_impact"], "suggestion": t["no_robots_sugg"], "url": robots_url, "examples": [robots_url]})

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
                        issues.append({"id": "sitemap_invalid", "category": "access", "severity": "Medium", "title": t["sitemap_invalid"], "desc": t["sitemap_invalid_desc"], "impact": t["sitemap_invalid_impact"], "suggestion": t["sitemap_invalid_sugg"], "url": sitemap_url, "examples": [sitemap_url]})
            else:
                if manual_sitemaps:
                    issues.append({"id": "no_sitemap", "category": "access", "severity": "Low", "title": t["no_sitemap"], "desc": f"{t['no_sitemap_desc']} (Status: {r.status_code})", "impact": t["no_sitemap_impact"], "suggestion": t["no_sitemap_sugg"], "url": sitemap_url, "examples": [sitemap_url]})
        except:
            if manual_sitemaps: issues.append({"id": "no_sitemap", "category": "access", "severity": "Low", "title": t["no_sitemap"], "desc": "Connection failed.", "impact": t["no_sitemap_impact"], "suggestion": t["no_sitemap_sugg"], "url": sitemap_url, "examples": [sitemap_url]})

    if not any_sitemap_valid and not manual_sitemaps:
         issues.append({"id": "no_sitemap", "category": "access", "severity": "Low", "title": t["no_sitemap"], "desc": t["no_sitemap_desc"], "impact": t["no_sitemap_impact"], "suggestion": t["no_sitemap_sugg"], "url": sitemap_urls_to_check[0], "examples": [sitemap_urls_to_check[0]]})

    # Favicon (Category: image_ux -> UX & Assets)
    has_favicon = False
    try:
        resp = requests.get(base_url, headers=headers, timeout=10, allow_redirects=True, verify=False)
        soup = BeautifulSoup(resp.content, 'html.parser')
        if soup.find('link', rel=lambda x: x and 'icon' in x.lower()): has_favicon = True
        else:
            r_ico = requests.get(urljoin(base_url, "/favicon.ico"), headers=headers, timeout=5, allow_redirects=True, stream=True, verify=False)
            if r_ico.status_code == 200 and int(r_ico.headers.get('content-length', 0)) > 0: has_favicon = True
            r_ico.close()
        
        if not has_favicon:
            issues.append({"id": "no_favicon", "category": "image_ux", "severity": "Low", "title": t["no_favicon"], "desc": t["no_favicon_desc"], "impact": t["no_favicon_impact"], "suggestion": t["no_favicon_sugg"], "url": base_url, "examples": [base_url]})
    except: pass

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
            issues.append({"id": "hreflang_invalid", "category": "indexability", "severity": "High", "title": t["hreflang_invalid"], "desc": f"{t['hreflang_invalid_desc']} ({', '.join(invalid_codes[:3])})", "impact": t["hreflang_invalid_impact"], "suggestion": t["hreflang_invalid_sugg"], "url": url})
        if not has_x_default:
            issues.append({"id": "hreflang_no_default", "category": "indexability", "severity": "Low", "title": t["hreflang_no_default"], "desc": t["hreflang_no_default_desc"], "impact": t["hreflang_no_default_impact"], "suggestion": t["hreflang_no_default_sugg"], "url": url})
    elif not sitemap_has_hreflang:
        issues.append({"id": "missing_hreflang", "category": "indexability", "severity": "Low", "title": t["missing_hreflang"], "desc": t["missing_hreflang_desc"], "impact": t["missing_hreflang_impact"], "suggestion": t["missing_hreflang_sugg"], "url": url})

    if not soup.find('meta', attrs={'name': 'viewport'}):
        issues.append({"id": "missing_viewport", "category": "technical", "severity": "Critical", "title": t["missing_viewport"], "desc": t["missing_viewport_desc"], "impact": t["missing_viewport_impact"], "suggestion": t["missing_viewport_sugg"], "url": url})

    canonical_tag = soup.find('link', attrs={'rel': 'canonical'})
    canonical_url = canonical_tag['href'] if canonical_tag else None
    if not canonical_url:
        issues.append({"id": "missing_canonical", "category": "indexability", "severity": "Medium", "title": t["missing_canonical"], "desc": t["missing_canonical_desc"], "impact": t["missing_canonical_impact"], "suggestion": t["missing_canonical_sugg"], "url": url})

    if not soup.find('script', type='application/ld+json'):
         # Smart Suggestion Logic
         parsed_u = urlparse(url)
         path = parsed_u.path.lower()
         spec_rec = "BreadcrumbList"
         if path == "/" or path == "": spec_rec = "Organization / WebSite"
         elif any(k in path for k in ["product", "shop", "item"]): spec_rec = "Product"
         elif any(k in path for k in ["blog", "news", "article"]): spec_rec = "Article"
         
         custom_sugg = f"{t['missing_jsonld_sugg']}\n(Detected type: {spec_rec})"
         issues.append({"id": "missing_jsonld", "category": "technical", "severity": "Medium", "title": t["missing_jsonld"], "desc": t["missing_jsonld_desc"], "impact": t["missing_jsonld_impact"], "suggestion": custom_sugg, "url": url})

    parsed_url = urlparse(url)
    path = parsed_url.path
    if '_' in path:
         issues.append({"id": "url_underscore", "category": "technical", "severity": "Low", "title": t["url_underscore"], "desc": t["url_underscore_desc"], "impact": t["url_underscore_impact"], "suggestion": t["url_underscore_sugg"], "url": url})
    if any(c.isupper() for c in path):
         issues.append({"id": "url_uppercase", "category": "technical", "severity": "Medium", "title": t["url_uppercase"], "desc": t["url_uppercase_desc"], "impact": t["url_uppercase_impact"], "suggestion": t["url_uppercase_sugg"], "url": url})

    js_links = soup.find_all('a', href=lambda x: x and x.lower().startswith('javascript:'))
    if js_links:
        issues.append({"id": "js_links", "category": "technical", "severity": "High", "title": t["js_links"], "desc": t["js_links_desc"], "impact": t["js_links_impact"], "suggestion": t["js_links_sugg"], "url": url, "meta": f"Count: {len(js_links)}"})

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
        issues.append({"id": "missing_alt", "category": "image_ux", "severity": "Medium", "title": t["missing_alt"], "desc": f"{missing_alt} {t['missing_alt_desc']}", "impact": t["missing_alt_impact"], "suggestion": t["missing_alt_sugg"], "url": url})
    if bad_alt_count > 0:
        issues.append({"id": "alt_bad_quality", "category": "image_ux", "severity": "Low", "title": t["alt_bad_quality"], "desc": t["alt_bad_quality_desc"], "impact": t["alt_bad_quality_impact"], "suggestion": t["alt_bad_quality_sugg"], "url": url, "evidence": f"{bad_alt_count} poor alts"})
    
    # 将 Static CLS Risk 归类为 cwv_performance
    if cls_risk_count > 0:
        issues.append({"id": "cls_risk", "category": "cwv_performance", "severity": "Medium", "title": t["cls_risk"], "desc": t["cls_risk_desc"], "impact": t["cls_risk_impact"], "suggestion": t["cls_risk_sugg"], "url": url, "evidence": f"{cls_risk_count} images"})

    links = soup.find_all('a', href=True)
    bad_anchors = ["click here", "read more", "learn more", "more", "here"]
    found_bad = []
    for link in links:
        at = link.get_text().strip().lower()
        if at in bad_anchors: found_bad.append(at)
    if found_bad:
        issues.append({"id": "anchor_bad_quality", "category": "image_ux", "severity": "Low", "title": t["anchor_bad_quality"], "desc": f"{t['anchor_bad_quality_desc']} ({len(found_bad)})", "impact": t["anchor_bad_quality_impact"], "suggestion": t["anchor_bad_quality_sugg"], "url": url})

    # --- Content ---
    title_tag = soup.title
    title = title_tag.string.strip() if title_tag and title_tag.string else None
    if not title:
        issues.append({"id": "missing_title", "category": "content", "severity": "High", "title": t["missing_title"], "desc": t["missing_title_desc"], "impact": t["missing_title_impact"], "suggestion": t["missing_title_sugg"], "url": url})
    elif len(title) < 10:
         issues.append({"id": "short_title", "category": "content", "severity": "Medium", "title": t["short_title"], "desc": t["short_title_desc"], "impact": t["short_title_impact"], "suggestion": t["short_title_sugg"], "url": url, "evidence": title})
    elif len(title) > 60:
         issues.append({"id": "long_title", "category": "content", "severity": "Low", "title": t["long_title"], "desc": t["long_title_desc"], "impact": t["long_title_impact"], "suggestion": t["long_title_sugg"], "url": url, "evidence": title})

    meta_desc = soup.find('meta', attrs={'name': 'description'})
    desc_content = meta_desc['content'].strip() if meta_desc and meta_desc.get('content') else None
    if not desc_content:
        issues.append({"id": "missing_desc", "category": "content", "severity": "High", "title": t["missing_desc"], "desc": t["missing_desc_desc"], "impact": t["missing_desc_impact"], "suggestion": t["missing_desc_sugg"], "url": url})
    elif len(desc_content) < 50:
        issues.append({"id": "short_desc", "category": "content", "severity": "Low", "title": t["short_desc"], "desc": t["short_desc_desc"], "impact": t["short_desc_impact"], "suggestion": t["short_desc_sugg"], "url": url, "evidence": desc_content})

    h1 = soup.find('h1')
    if not h1: issues.append({"id": "missing_h1", "category": "content", "severity": "High", "title": t["missing_h1"], "desc": t["missing_h1_desc"], "impact": t["missing_h1_impact"], "suggestion": t["missing_h1_sugg"], "url": url})

    if status_code == 200:
        error_kws = ["page not found", "404 error", "页面未找到"]
        is_s404 = False
        if title and any(k in title.lower() for k in error_kws): is_s404 = True
        elif soup.find('h1') and any(k in soup.find('h1').get_text().lower() for k in error_kws): is_s404 = True
        if is_s404:
            issues.append({"id": "soft_404", "category": "access", "severity": "Critical", "title": t["soft_404"], "desc": t["soft_404_desc"], "impact": t["soft_404_impact"], "suggestion": t["soft_404_sugg"], "url": url})

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
    
    # 1. Site Level Checks
    try:
        site_issues, sitemap_has_hreflang = check_site_level_assets(
            start_url, lang=lang, manual_robots=manual_robots, manual_sitemaps=manual_sitemaps
        )
        all_issues.extend(site_issues)
        st.session_state['sitemap_hreflang_found'] = sitemap_has_hreflang
    except Exception as e:
        pass

    # 2. CWV
    if psi_key:
        with st.spinner(TRANSLATIONS[lang]["psi_fetching"]):
            cwv_data = fetch_psi_data(start_url, psi_key)
            if cwv_data and "error" not in cwv_data: 
                st.session_state['cwv_data'] = cwv_data
                cwv_issues = check_cwv_issues(cwv_data, start_url, lang)
                all_issues.extend(cwv_issues)
            else: 
                st.session_state['cwv_data'] = None

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
                all_issues.append({"id": "http_3xx", "category": "access", "severity": "Medium", "title": t["3xx_title"], "desc": f"{t['3xx_desc']} -> {current_url}", "impact": t["3xx_impact"], "suggestion": t["3xx_sugg"], "url": url, "examples": [url]})

            # 2. 4xx/5xx
            if final_status >= 400:
                is_5xx = final_status >= 500
                all_issues.append({"id": "http_5xx" if is_5xx else "http_4xx", "category": "access", "severity": "Critical" if is_5xx else "High", "title": t["5xx_title"] if is_5xx else t["4xx_title"], "desc": f"{t['5xx_desc'] if is_5xx else t['4xx_desc']} ({final_status})", "impact": t["5xx_impact"] if is_5xx else t["4xx_impact"], "suggestion": t["5xx_sugg"] if is_5xx else t["4xx_sugg"], "url": url, "examples": [url]})

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
                                # 重复内容特殊标记
                                dup_issue = {
                                    "id": "duplicate", "category": "indexability", 
                                    "severity": "High", "title": t["duplicate"], 
                                    "desc": f"{t['duplicate_desc']}", 
                                    "impact": t["duplicate_impact"], 
                                    "suggestion": t["duplicate_sugg"], 
                                    "url": current_url, 
                                    "meta": f"Duplicate of: {original_url}" # Key for visualization
                                }
                                page_issues.append(dup_issue)
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
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(7), Inches(4), Inches(5.8), Inches(2.5)) # Moved down
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
        label = slide.shapes.add_textbox(Inches(7), Inches(3.6), Inches(3), Inches(0.3))
        p = label.text_frame.add_paragraph()
        p.text = txt["serp_sim_title"]
        set_font(p.font, 12, True, RGBColor(100, 100, 100))

    def draw_rich_snippet_preview(slide, url):
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(7), Inches(4), Inches(5.8), Inches(2.5)) # Moved down
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
        sev_color = RGBColor(220, 53, 69) if issue['severity'] == "Critical" else RGBColor(253, 126, 20)
        sev_box = slide.shapes.add_textbox(Inches(11), Inches(0.35), Inches(2), Inches(0.5))
        p = sev_box.text_frame.add_paragraph()
        p.text = f"{issue['severity']}"
        p.alignment = PP_ALIGN.CENTER
        set_font(p.font, 18, True, sev_color)
        
        # Category
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
        p.text = issue['impact']
        set_font(p.font, 14, False, RGBColor(220, 53, 69))

        # Right Column Split
        ex_title = slide.shapes.add_textbox(Inches(7), Inches(1.5), Inches(5.8), Inches(0.5))
        p = ex_title.text_frame.add_paragraph()
        p.text = txt["ppt_slide_ex_title"]
        set_font(p.font, 18, True, RGBColor(30, 30, 30))
        
        ex_box = slide.shapes.add_textbox(Inches(7), Inches(2.0), Inches(5.8), Inches(1.5)) 
        tf = ex_box.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
        
        for idx, url in enumerate(issue['examples'][:4]): 
            p = tf.add_paragraph()
            # Visualize Duplicate Logic
            if "duplicate" in issue['id']:
                 parts = url.split("Duplicate of:")
                 if len(parts) > 1:
                     p.text = f"{parts[0].strip()}\n   ↳ Original: {parts[1].strip()}"
                 else:
                     p.text = f"• {url}"
            else:
                 p.text = f"• {url}"
            
            set_font(p.font, 11, False, RGBColor(0, 102, 204))
            p.space_after = Pt(6)

        # Visualization
        is_serp = any(k in issue['title'] for k in ["Title", "标题", "Meta", "元描述"])
        is_rich = any(k in issue['title'] for k in ["Schema", "Structured", "结构化"])
        
        ev = issue.get('example_evidence', '')
        ex_url = issue['examples'][0] if issue['examples'] else "example.com"
        if "Duplicate" in issue['title'] and "Duplicate of:" in ex_url: 
             ex_url = ex_url.split("Duplicate of:")[0].strip()

        if is_serp:
            draw_serp_preview(slide, issue['title'], ev, ex_url)
        elif is_rich:
            draw_rich_snippet_preview(slide, ex_url)

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
                    "id": i.get("id", "unknown"),
                    "title": t, "severity": i['severity'], "desc": i['desc'], 
                    "suggestion": i['suggestion'], "count": 0, "examples": [],
                    "example_evidence": i.get("evidence", ""),
                    "category": i.get("category", "content"),
                    "impact": i.get("impact", "")
                }
            grouped[t]['count'] += 1
            if len(grouped[t]['examples']) < 5: 
                # Fixed: Only try to split if "Duplicate of:" exists
                if "meta" in i and "Duplicate of:" in i['meta']: 
                     grouped[t]['examples'].append(f"{i['url']} Duplicate of: {i['meta'].split('Duplicate of: ')[1]}")
                else: 
                     grouped[t]['examples'].append(i['url'])
        
        # Sort by Category -> Severity -> Count
        sov_order = SEVERITY_ORDER
        cat_order = {k: v for v, k in enumerate(CATEGORY_ORDER)}
        
        slides = sorted(list(grouped.values()), key=lambda x: (
            cat_order.get(x['category'], 99), 
            get_issue_priority(x['id']), # NEW: Precise ordering
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
                
                st.markdown(f"**{ui['ppt_business_impact']}**") 
                st.error(s['impact']) 
                
                st.info(f"{ui['ppt_sugg']} {s['suggestion']}")
            with c2:
                is_serp = any(k in s['title'] for k in ["Title", "标题", "Meta", "元描述"])
                is_rich = any(k in s['title'] for k in ["Schema", "Structured", "结构化"])
                
                if is_serp:
                    st.markdown(f"**{ui.get('serp_sim_title', 'SERP Preview')}**")
                    ev = s.get('example_evidence', '')
                    ex_url = s['examples'][0] if s['examples'] else "example.com"
                    if "Duplicate" in ex_url: ex_url = ex_url.split("Duplicate of:")[0].strip()
                    
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
                    for ex in s['examples']: 
                        # Web View Format
                        if "Duplicate of:" in ex:
                            parts = ex.split("Duplicate of:")
                            st.markdown(f"- `{parts[0].strip()}`  \n  ↳ **Original:** `{parts[1].strip()}`")
                        else:
                            st.markdown(f"- `{ex}`")

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
