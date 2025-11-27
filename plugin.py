import sys
import re
import os
import xml.etree.ElementTree as ET

# Try importing PyQt5, fallback to PyQt6 if needed (Sigil environment usually provides one)
try:
    from PyQt5.QtWidgets import QApplication, QMessageBox
    from PyQt5.QtCore import Qt
except ImportError:
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from PyQt6.QtCore import Qt
    except ImportError:
        # Fallback if neither is found (should not happen in standard Sigil)
        # We can define a dummy or re-raise
        raise ImportError("Could not find PyQt5 or PyQt6. This plugin requires a standard Sigil environment.")

def cn2an_simple(text):
    """
    Simple Chinese number to Arabic number converter.
    Supports basic numbers up to roughly 100,000.
    """
    cn_nums = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
               '六': 6, '七': 7, '八': 8, '九': 9}
    cn_units = {'十': 10, '百': 100, '千': 1000, '万': 10000}

    if text.isdigit():
        return int(text)

    # Basic check for direct mapping (e.g., '一' -> 1)
    if len(text) == 1 and text in cn_nums:
        return cn_nums[text]

    result = 0
    temp_val = 0
    current_val = 0

    # Simple parser
    for char in text:
        if char in cn_nums:
            current_val = cn_nums[char]
        elif char in cn_units:
            unit_val = cn_units[char]
            if current_val == 0 and unit_val == 10:
                # Handling '十' at start (e.g., 十一 -> 11)
                current_val = 1

            if unit_val > temp_val and temp_val > 0:
                 # Handling large units like 万 (e.g., 一百二十万)
                 result += (temp_val + current_val) * unit_val
                 temp_val = 0
                 current_val = 0
            else:
                 temp_val += current_val * unit_val
                 current_val = 0

    result += temp_val + current_val
    return result

def get_nav_id(bk):
    """
    Finds the Navigation Document ID by parsing the OPF file.
    """
    opf_id = None
    opf_content = None

    try:
        if hasattr(bk, 'manifest_iter'):
            iterator = bk.manifest_iter()
        else:
            iterator = []

        for file_id in iterator:
            if file_id.lower().endswith('.opf'):
                 opf_id = file_id
                 break

            try:
                href = bk.id_to_href(file_id)
                if href and href.lower().endswith('.opf'):
                    opf_id = file_id
                    break
            except:
                continue
    except Exception:
        pass

    if not opf_id:
        return None

    try:
        opf_content = bk.readfile(opf_id)
    except:
        return None

    if not opf_content:
        return None

    match = re.search(r'<item[^>]*properties="[^"]*\bnav\b[^"]*"[^>]*>', opf_content)
    if match:
        item_tag = match.group(0)
        href_match = re.search(r'href="([^"]+)"', item_tag)
        if href_match:
            return bk.href_to_id(href_match.group(1))

    return None

def extract_text_from_nav(nav_content):
    """
    Extracts all text content from the nav.xhtml using ElementTree.
    """
    texts = []
    try:
        content_clean = re.sub(r' xmlns="[^"]+"', '', nav_content, count=1)
        parser = ET.XMLParser(encoding="utf-8")
        root = ET.fromstring(content_clean, parser=parser)

        for elem in root.iter():
            if elem.text and elem.text.strip():
                texts.append(elem.text.strip())
            if elem.tail and elem.tail.strip():
                texts.append(elem.tail.strip())

    except Exception:
        matches = re.findall(r'>([^<]+)<', nav_content)
        for m in matches:
            t = m.strip()
            if t:
                texts.append(t)

    return texts

def show_msg(title, text, icon_type="info"):
    """
    Helper to show a QMessageBox in Sigil
    """
    # Ensure QApplication exists
    app = QApplication.instance()
    if not app:
        # In strictly headless plugins without UI wrapper this might fail,
        # but Sigil plugins run in the main GUI thread usually.
        app = QApplication(sys.argv)

    msg = QMessageBox()
    msg.setWindowTitle(title)

    # Style the text with HTML for centering and bolding as per request
    # Use simple HTML
    msg.setText(text)

    if icon_type == "warning":
        msg.setIcon(QMessageBox.Warning)
    else:
        msg.setIcon(QMessageBox.Information)

    msg.setStandardButtons(QMessageBox.Ok)
    msg.exec()

def run(bk):
    nav_id = get_nav_id(bk)
    if not nav_id:
        for test_href in ['nav.xhtml', 'OEBPS/nav.xhtml', 'Text/nav.xhtml']:
             maybe_id = bk.href_to_id(test_href)
             if maybe_id:
                 nav_id = maybe_id
                 break

    if not nav_id:
        show_msg("Error", "<h3>无法找到导航文档 (nav.xhtml)</h3><p>Could not find Navigation Document.</p>", "warning")
        return 0

    nav_content = bk.readfile(nav_id)
    texts = extract_text_from_nav(nav_content)

    pattern = re.compile(r'第\s*([0-9]+|[零一二三四五六七八九十百千万]+)\s*章')

    found_chapters = []

    for t in texts:
        m = pattern.search(t)
        if m:
            num_str = m.group(1)
            try:
                num = cn2an_simple(num_str)
                found_chapters.append(num)
            except:
                pass

    if not found_chapters:
        show_msg("Result", "<h3>未发现符合“第+序号+章”格式的章节</h3><p>No chapters found matching the pattern.</p>")
        return 0

    found_chapters.sort()
    found_chapters = sorted(list(set(found_chapters)))

    if not found_chapters:
        return 0

    start = found_chapters[0]
    end = found_chapters[-1]

    full_set = set(range(start, end + 1))
    found_set = set(found_chapters)

    missing = sorted(list(full_set - found_set))

    if missing:
        msg_list = [str(x) for x in missing]
        if len(msg_list) > 20:
             missing_str = ", ".join(msg_list[:20]) + f" ... (total {len(msg_list)})"
        else:
             missing_str = ", ".join(msg_list)

        # Format similar to success message but for warning
        html = (f"<h3 style='text-align: center;'>检测到章节遗漏 (Missing Chapters)</h3>"
                f"<p style='text-align: center;'>Missing: {missing_str}</p>")
        show_msg("Found Missing Chapters", html, "warning")
    else:
        # Match the requested UI style:
        # "检查完成，序号连续。" (Bold/Header)
        # "Checked X chapters from Y to Z. No gaps found."
        html = (f"<h3 style='text-align: center;'>检查完成，序号连续。</h3>"
                f"<p style='text-align: center;'>Checked <b>{len(found_chapters)}</b> chapters from <b>{start}</b> to <b>{end}</b>.<br>"
                f"No gaps found.</p>")
        show_msg("Success", html)

    return 0
