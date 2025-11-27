import sys
import re
import os
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import messagebox

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

    # Try to find OPF file ID
    # Use bk.manifest_iter() which yields file IDs
    try:
        # Check if manifest_iter exists, if not fall back safely (unlikely in Sigil)
        if hasattr(bk, 'manifest_iter'):
            iterator = bk.manifest_iter()
        else:
            # Fallback for very old APIs or if the wrapper is different
            # Some wrappers might use iter(bk.manifest)
            # But let's assume standard Sigil plugin API
            iterator = []

        for file_id in iterator:
            # Check ID itself first
            if file_id.lower().endswith('.opf'):
                 opf_id = file_id
                 break
            
            # Check HREF
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

    # Parse OPF XML to find <item ... properties="nav" ... />
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
        # Remove XML namespaces to simplify tag finding
        content_clean = re.sub(r' xmlns="[^"]+"', '', nav_content, count=1)
        
        parser = ET.XMLParser(encoding="utf-8")
        root = ET.fromstring(content_clean, parser=parser)
        
        # Recursively find text
        for elem in root.iter():
            if elem.text and elem.text.strip():
                texts.append(elem.text.strip())
            if elem.tail and elem.tail.strip():
                texts.append(elem.tail.strip())
                
    except Exception:
        # Fallback to regex if XML parsing fails
        matches = re.findall(r'>([^<]+)<', nav_content)
        for m in matches:
            t = m.strip()
            if t:
                texts.append(t)
                
    return texts

def run(bk):
    # Initialize Tkinter root (hidden)
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception as e:
        # If Tkinter fails (e.g. Linux without display), print error to stdout/stderr
        print(f"Tkinter error: {e}")
        return -1

    nav_id = get_nav_id(bk)
    if not nav_id:
        # Fallback check: standard paths
        for test_href in ['nav.xhtml', 'OEBPS/nav.xhtml', 'Text/nav.xhtml']:
             maybe_id = bk.href_to_id(test_href)
             if maybe_id:
                 nav_id = maybe_id
                 break
    
    if not nav_id:
        messagebox.showerror("Error", "无法找到导航文档 (nav.xhtml). \nCould not find Navigation Document.")
        return 0

    nav_content = bk.readfile(nav_id)
    texts = extract_text_from_nav(nav_content)
    
    # Regex for "第X章"
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
        messagebox.showinfo("Result", "未发现符合“第+序号+章”格式的章节。\nNo chapters found matching the pattern.")
        return 0

    # Sort and check for gaps
    found_chapters.sort()
    
    # Remove duplicates
    found_chapters = sorted(list(set(found_chapters)))
    
    if not found_chapters:
        return 0

    start = found_chapters[0]
    end = found_chapters[-1]
    
    # Ideal sequence from start to end
    full_set = set(range(start, end + 1))
    found_set = set(found_chapters)
    
    missing = sorted(list(full_set - found_set))
    
    if missing:
        msg_list = [str(x) for x in missing]
        if len(msg_list) > 20:
             display_msg = ", ".join(msg_list[:20]) + f" ... (total {len(msg_list)} missing)"
        else:
             display_msg = ", ".join(msg_list)
             
        messagebox.showwarning("Found Missing Chapters", f"检测到以下章节遗漏 (Missing Chapters):\n\n{display_msg}")
    else:
        messagebox.showinfo("Success", f"检查完成，序号连续。\nChecked {len(found_chapters)} chapters from {start} to {end}. No gaps found.")

    return 0
