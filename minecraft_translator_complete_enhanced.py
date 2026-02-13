# -*- coding: utf-8 -*-
# minecraft_translator_complete_enhanced.py - 增强版
try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox, filedialog
except Exception:  # Allow headless/Qt-only runtime without tkinter.
    tk = None
    ttk = None
    scrolledtext = None
    messagebox = None
    filedialog = None
import json
import os
import time
from datetime import datetime
import webbrowser
from pathlib import Path
import sys
import re
import threading
import queue
import hashlib
import random
import urllib.parse
import urllib.request
from enum import Enum
# ==================== 语言检测枚举 ====================
class Language(Enum):
    UNKNOWN = "unknown"
    ENGLISH = "en"
    CHINESE = "zh"
    JAPANESE = "ja"
    KOREAN = "ko"
    FRENCH = "fr"
    GERMAN = "de"
    SPANISH = "es"
    RUSSIAN = "ru"
# ==================== 语言检测器 ====================
class LanguageDetector:
    def __init__(self):
        # 语言特征模式
        self.language_patterns = {
            Language.ENGLISH: [
                r'[A-Za-z]',  # 英文字母
                r'\b(the|and|you|that|have|for|not|with|this|but)\b',
                r'\b(is|are|was|were|be|been|being)\b'
            ],
            Language.CHINESE: [
                r'[\u4e00-\u9fff]',  # 中文汉字
                r'[\u3400-\u4dbf]',  # 扩展A区
                r'[\U00020000-\U0002A6DF]',  # 扩展B区
            ],
            Language.JAPANESE: [
                r'[\u3040-\u309f]',  # 平假名
                r'[\u30a0-\u30ff]',  # 片假名
                r'[\u4e00-\u9fff]',  # 汉字（共享）
            ],
            Language.KOREAN: [
                r'[\uac00-\ud7af]',  # 韩文音节
                r'[\u1100-\u11ff]',  # 韩文字母
                r'[\u3130-\u318f]',  # 兼容字母
            ],
            Language.RUSSIAN: [
                r'[\u0400-\u04FF]',
            ],
        }
        
    def detect(self, text):
        """检测文本语言"""
        if not text or not text.strip():
            return Language.UNKNOWN
        
        text = text.strip()
        
        # 快速检查中文
        if self._contains_chinese(text):
            return Language.CHINESE
        
        # 检查其他语言
        scores = {}
        text_lower = text.lower()
        
        for lang, patterns in self.language_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower, re.IGNORECASE))
                score += matches
            
            # 增加权重给特殊字符
            if lang == Language.ENGLISH:
                score += len(re.findall(r'[A-Za-z]', text)) * 0.5
            elif lang == Language.CHINESE:
                score += len(re.findall(r'[\u4e00-\u9fff]', text)) * 2
            
            scores[lang] = score
        
        # 找到得分最高的语言
        if scores:
            best_lang = max(scores.items(), key=lambda x: x[1])
            if best_lang[1] > 0:
                return best_lang[0]
        
        # 默认返回英文（如果包含字母）
        if re.search(r'[A-Za-z]', text):
            return Language.ENGLISH
        
        return Language.UNKNOWN
    
    def _contains_chinese(self, text):
        """检查是否包含中文"""
        return bool(re.search(r'[\u4e00-\u9fff]', text))
    
    def should_translate(self, text, target_lang='zh-CN'):
        """判断是否需要翻译"""
        detected = self.detect(text)
        target = Language.UNKNOWN
        
        # 映射目标语言
        lang_map = {
            'zh-CN': Language.CHINESE,
            'en': Language.ENGLISH,
            'ja': Language.JAPANESE,
            'ko': Language.KOREAN,
            'fr': Language.FRENCH,
            'de': Language.GERMAN,
            'es': Language.SPANISH,
            'ru': Language.RUSSIAN,
        }
        
        if target_lang in lang_map:
            target = lang_map[target_lang]
        
        # 如果检测到的语言和目标语言相同，不需要翻译
        if detected == target:
            return False
        
        # 如果检测到未知语言，尝试翻译
        if detected == Language.UNKNOWN:
            return True
        
        # 中英文互译
        if (detected == Language.CHINESE and target == Language.ENGLISH) or \
           (detected == Language.ENGLISH and target == Language.CHINESE):
            return True
        
        # 其他情况都翻译
        return True
# ==================== 消息过滤器 ====================
class MessageFilter:
    """
    过滤器（可配置开关）：
    - 过滤开关关闭时：不做任何过滤，所有日志行都放行（用于排查/调试）。
    - 过滤开关开启时：默认只保留“玩家聊天”，可选保留“系统公告/奖励提示”等。
    """
    def __init__(self, enabled: bool = True, keep_system: bool = False, keep_rewards: bool = False):
        self.enabled = bool(enabled)
        self.keep_system = bool(keep_system)
        self.keep_rewards = bool(keep_rewards)
        # 这些基本都是“非玩家聊天”的日志噪音（可按需继续加）
        self._base_filter_patterns = [
            # Badlion/Lunar/???????
            r'<Opening menu>.*',
            r'<Loading>.*',
            r'Opening menu:\s+class\s+.*',
            r'Worker done, connecting to .*',
            r'Connecting to .*',
            r'\[LOADING-SCREEN\].*',
            r'Updating active cosmetics list\.\.\.',
            r'GL\d+\s+supported',
            r'Item entity \d+ has no item\?!',
            r'-- Start Memory Debug --.*',
            r'-- End Memory Debug --.*',
            r'^Max:\s+\d+\s*\(.*\)$',
            r'^Total:\s+\d+\s*\(.*\)$',
            r'^Free:\s+\d+\s*\(.*\)$',
            r'^<Max>\s+\d+.*',
            r'^<Total>\s+\d+.*',
            r'^<Free>\s+\d+.*',
            r'Data sync response failed:.*',
            # ??/??/??
            r"<Can't ping .*?>\s+Timed out",
            r"Can't ping .*",
            r'<Update Connection State>\s+\d+',
            r'<Update Connection Server>\s+.*',
            r'<Update connection status json2>\s+.*',
            # ???/??????????????????????????
            r'^\s*Bed Wars\s*$',
            # ?????/??/?????
            r'^\s*/\S+.*',  # /report /rejoin ?
            r'^[^a-zA-Z0-9\u4e00-\u9fff]{1,3}$',
                    r'^<BLC>.*',
            r'^<Opponent>.*',
        ]
        # 奖励/经验/代币提示（默认过滤；勾选“保留奖励提示”时不过滤）
        self._reward_filter_patterns = [
            r'^\+\d+\s+tokens!\s*\(.*\).*',
            r'^\+\d+\s+Bed Wars XP\s*\(.*\).*',
            r'^Tokens just earned DOUBLED.*',
        ]
        # 系统公告（可选保留：进服退服/成就等）
        self.system_keep_patterns = [
            r'.*joined the game.*',
            r'.*left the game.*',
            r'.*has made the advancement.*',
            r'.*has completed.*',
            r'.*achievement.*',
            r'.*advancement.*',
            r'玩家.*加入游戏',
            r'玩家.*离开游戏',
            r'完成了进度',
            r'获得了成就',
        ]
        # 玩家聊天（白名单：尽量精确；允许带段位/前缀）
        # 说明：很多客户端会在聊天前加 “[MVP+] ” 这类前缀，或在日志里残留颜色码。
        self.chat_patterns = [
            # <玩家> 消息（可带若干个 [前缀]，允许空 [] 和特殊字符）
            r'^(?:\[[^\]]*\]\s*)*<[^>]{1,32}>\s*.+$',
            # [xxx] [xxx/CHAT]: <玩家> 消息   /  [CHAT] <玩家> 消息（保留原兼容）
            r'^\[.*?\]\s*\[.*?/CHAT\]:\s*.+$',
            r'^\[CHAT\]\s*.+$',
            # name: message（可带若干个 [前缀]，允许空 [] 和特殊字符）
            r'^(?:\[[^\]]*\]\s*)*[A-Za-z0-9_]{3,16}\s*:\s*.+$',
        ]

        # Chat source detection patterns
        self.chat_source_patterns = {
            'private': [
                r'whisper', r'whispers', r'tell', r'msg', r'pm', r'private',
                r'??', r'???', r'???', r'???',
            ],
            'team': [
                r'team', r'\[TEAM\]', r'??', r'??',
            ],
            'guild': [
                r'guild', r'\[GUILD\]', r'??', r'??',
            ],
        }
        # “name: message” 格式（只在 name 像 MC ID 时才视为玩家聊天；支持可选前缀）
        self.colon_chat = re.compile(r'^(?:\[[^\]]+\]\s*)*([A-Za-z0-9_]{3,16})\s*:\s*(.+)$')
        # 对外展示用（供“详细分析”窗口显示）
        self.filter_patterns = []
        self.keep_patterns = []
        self._rebuild_patterns()
    def set_options(self, enabled=None, keep_system=None, keep_rewards=None):
        """运行时更新过滤选项（UI 勾选后调用）。"""
        if enabled is not None:
            self.enabled = bool(enabled)
        if keep_system is not None:
            self.keep_system = bool(keep_system)
        if keep_rewards is not None:
            self.keep_rewards = bool(keep_rewards)
        self._rebuild_patterns()
    def _rebuild_patterns(self):
        # 当前生效的过滤模式
        pats = list(self._base_filter_patterns)
        if not self.keep_rewards:
            pats.extend(self._reward_filter_patterns)
        self.filter_patterns = pats
        # 当前生效的保留模式（供 UI 展示）
        keep = list(self.chat_patterns)
        if self.keep_system:
            keep.extend(self.system_keep_patterns)
        self.keep_patterns = keep
    def should_keep(self, raw_line: str) -> bool:
        # 过滤总开关关闭：全部放行
        if not self.enabled:
            return True
        line = (raw_line or '').strip()
        if not line:
            return False
        # 先做一次“粗过滤”
        cleaned = self.clean_message(line)
        for pat in self.filter_patterns:
            if re.search(pat, line, re.IGNORECASE) or re.search(pat, cleaned, re.IGNORECASE):
                return False
        # 系统公告（可选）
        if self.is_system_message(cleaned):
            return True
        # 玩家聊天
        if self.is_player_chat(cleaned):
            return True
        # 其它一律丢弃（只保留玩家聊天/可选系统公告）
        return False
    def is_player_chat(self, cleaned: str) -> bool:
        if not cleaned:
            return False
        # 排除伪“玩家标签”的系统统计（例如 <Max>/<Total>/<Free>）
        if re.match(r'^<(Max|Total|Free)>\b', cleaned, flags=re.IGNORECASE):
            return False
        # 明确聊天格式
        for pat in self.chat_patterns:
            if re.search(pat, cleaned):
                # 再做个“内容像聊天”的检查：至少包含一个字母/汉字
                return bool(re.search(r'[A-Za-z\u4e00-\u9fff]', cleaned))
        # name: message（name 必须像 MC ID）
        m = self.colon_chat.match(cleaned)
        if m:
            name = m.group(1).strip()
            msg = m.group(2).strip()
            if re.match(r'^(Max|Total|Free)$', name, flags=re.IGNORECASE):
                return False
            return bool(msg) and bool(re.search(r'[A-Za-z\u4e00-\u9fff]', msg))
        return False
    def clean_message(self, message: str) -> str:
        """清理消息中的无用部分（时间戳/INFO/WARN/CHAT标记等）"""
        patterns_to_remove = [
            r'^\[\d{2}:\d{2}:\d{2}\]\s*',
            r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]\s*',
            # Minecraft formatting codes (may appear as '§b' or as stripped single-letter prefix)
            # NOTE: we also remove color/style codes globally further below.
            r'^§[0-9a-fk-or]\s*',
            r'^([0-9a-fk-or])(?=\[)',
            r'\[.*?INFO\]:\s*',
            r'\[.*?WARN\]:\s*',
            r'\[.*?ERROR\]:\s*',
            r'\[Client thread\]:\s*',
            r'\[Server thread\]:\s*',
            r'\[CHAT\]\s*',
        ]
        cleaned = message
        for pat in patterns_to_remove:
            cleaned = re.sub(pat, '', cleaned, flags=re.IGNORECASE)
        # Remove Minecraft color/style codes anywhere in the line (e.g. "§b", "§l").
        # These codes frequently appear before rank tags and player names, and will otherwise
        # break the player-chat detection (e.g. "§b[MVP+] name§f: msg").
        cleaned = re.sub(r'§[0-9A-FK-ORa-fk-or]', '', cleaned)
        cleaned = cleaned.replace('§', '')
        # Some launchers/log formats may lose the '§' and leave a single code letter right
        # before a bracket, e.g. "b[MVP+] name: msg". Remove such standalone code letters.
        cleaned = re.sub(r'(?<![A-Za-z0-9_])[0-9A-FK-ORa-fk-or](?=\[)', '', cleaned)
        return cleaned.strip() or message.strip()
    def extract_player_message(self, message: str):
        """从消息中提取玩家名和消息内容（仅对玩家聊天有意义）"""
        cleaned = self.clean_message(message)
        patterns = [
            # 允许前面带若干个 [前缀]（允许空 [] 和特殊字符）
            r'^(?:\[[^\]]*\]\s*)*<([^>]+)>\s*(.*)$',
            r'^\[.*?\]\s*\[.*?/CHAT\]:\s*<([^>]+)>\s*(.*)$',
            r'^(?:\[[^\]]*\]\s*)*([A-Za-z0-9_]{3,16})\s*:\s*(.*)$',
        ]
        for pat in patterns:
            m = re.match(pat, cleaned)
            if m:
                player = m.group(1).strip()
                msg = m.group(2).strip()
                if re.match(r'^(Max|Total|Free)$', player, flags=re.IGNORECASE):
                    return None, cleaned
                return player, msg
        return None, cleaned
    def is_system_message(self, message: str) -> bool:
        if not self.keep_system:
            return False
        for kw in self.system_keep_patterns:
            if re.search(kw, message, re.IGNORECASE):
                return True
        return False
# ==================== 百度翻译API ====================
class BaiduTranslator:
    def detect_chat_source(self, raw_line: str, cleaned: str) -> str:
        """Return one of: public/team/private/guild/system."""
        if self.is_system_message(cleaned or ''):
            return 'system'
        txt = (raw_line or '') + ' ' + (cleaned or '')
        # Private has highest priority
        for pat in self.chat_source_patterns.get('private', []):
            if re.search(pat, txt, re.IGNORECASE):
                return 'private'
        for pat in self.chat_source_patterns.get('team', []):
            if re.search(pat, txt, re.IGNORECASE):
                return 'team'
        for pat in self.chat_source_patterns.get('guild', []):
            if re.search(pat, txt, re.IGNORECASE):
                return 'guild'
        return 'public'

    def __init__(self, app_id=None, secret_key=None):
        """
        初始化百度翻译API
        申请地址: https://api.fanyi.baidu.com/
        """
        self.app_id = app_id or ""
        self.secret_key = secret_key or ""
        self.lang_detector = LanguageDetector()
        
    def translate(self, text, from_lang='auto', to_lang='zh'):
        """翻译文本"""
        print(f"[百度翻译] 开始翻译: '{text}' (from: {from_lang} -> to: {to_lang})")
        
        # 自动检测源语言
        if from_lang == 'auto':
            detected = self.lang_detector.detect(text)
            if detected != Language.UNKNOWN:
                from_lang = detected.value
                print(f"[百度翻译] 自动检测语言: {from_lang}")
        
        # 检查是否需要翻译
        if not self.should_translate(text, to_lang):
            print(f"[百度翻译] 无需翻译，返回原文本")
            return text, None
        
        if not self.app_id or not self.secret_key:
            error_msg = "请先配置百度翻译API密钥"
            print(f"[百度翻译] 错误: {error_msg}")
            return None, error_msg
        
        if not text or not text.strip():
            error_msg = "文本为空"
            print(f"[百度翻译] 错误: {error_msg}")
            return None, error_msg
        
        try:
            salt = str(random.randint(32768, 65536))
            sign_str = self.app_id + text + salt + self.secret_key
            sign = hashlib.md5(sign_str.encode()).hexdigest()
            
            params = {
                'q': text,
                'from': from_lang,
                'to': to_lang,
                'appid': self.app_id,
                'salt': salt,
                'sign': sign
            }
            
            url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
            query_string = urllib.parse.urlencode(params)
            full_url = f"{url}?{query_string}"
            
            print(f"[百度翻译] 请求URL: {full_url}")
            
            req = urllib.request.Request(full_url)
            response = urllib.request.urlopen(req, timeout=10)
            result = json.loads(response.read().decode())
            
            print(f"[百度翻译] 响应结果: {result}")
            
            if 'trans_result' in result:
                translated_text = result['trans_result'][0]['dst']
                print(f"[百度翻译] 翻译成功: '{text}' -> '{translated_text}'")
                return translated_text, None
            else:
                error_msg = result.get('error_msg', '翻译失败')
                error_code = result.get('error_code', '未知错误')
                print(f"[百度翻译] 错误: {error_code} - {error_msg}")
                return None, f"百度翻译错误({error_code}): {error_msg}"
                
        except Exception as e:
            error_msg = f"翻译请求失败: {str(e)}"
            print(f"[百度翻译] 异常: {error_msg}")
            return None, error_msg
    
    def should_translate(self, text, target_lang):
        """判断是否需要翻译"""
        return self.lang_detector.should_translate(text, target_lang)
# ==================== Google免费翻译 ====================
class GoogleTranslator:
    def __init__(self):
        self.lang_detector = LanguageDetector()
        
    def translate(self, text, from_lang='auto', to_lang='zh-CN'):
        """使用Google翻译API"""
        print(f"[Google翻译] 开始翻译: '{text}' (from: {from_lang} -> to: {to_lang})")
        
        # 自动检测源语言
        if from_lang == 'auto':
            detected = self.lang_detector.detect(text)
            if detected != Language.UNKNOWN:
                from_lang = detected.value
                print(f"[Google翻译] 自动检测语言: {from_lang}")
        
        # 检查是否需要翻译
        if not self.should_translate(text, to_lang):
            print(f"[Google翻译] 无需翻译，返回原文本")
            return text, None
        
        if not text or not text.strip():
            error_msg = "文本为空"
            print(f"[Google翻译] 错误: {error_msg}")
            return None, error_msg
        
        try:
            # 简单实现 - 使用网页版接口
            encoded_text = urllib.parse.quote(text)
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={from_lang}&tl={to_lang}&dt=t&q={encoded_text}"
            
            print(f"[Google翻译] 请求URL: {url}")
            
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            response = urllib.request.urlopen(req, timeout=10)
            result = json.loads(response.read().decode())
            
            print(f"[Google翻译] 响应结果: {result}")
            
            # 解析结果
            translated_text = ''
            if result and result[0]:
                for segment in result[0]:
                    if segment[0]:
                        translated_text += segment[0]
            
            if translated_text:
                print(f"[Google翻译] 翻译成功: '{text}' -> '{translated_text}'")
                return translated_text, None
            else:
                error_msg = "解析翻译结果失败"
                print(f"[Google翻译] 错误: {error_msg}")
                return None, error_msg
            
        except Exception as e:
            error_msg = f"Google翻译失败: {str(e)}"
            print(f"[Google翻译] 异常: {error_msg}")
            return None, error_msg
    
    def should_translate(self, text, target_lang):
        """判断是否需要翻译"""
        return self.lang_detector.should_translate(text, target_lang)
# ==================== 增强版日志监控模块 ====================
class EnhancedMinecraftLogMonitor:
    def __init__(self, callback=None):
        self.callback = callback
        self.log_file = None
        self.last_position = 0
        self.running = False
        self.thread = None
        self.last_messages = []  # 记录最近消息，避免重复处理
        self.message_filter = MessageFilter()

        self.lang_detector = LanguageDetector()
        
        # Minecraft日志路径
        self.default_paths = [
            Path.home() / "AppData" / "Roaming" / ".minecraft" / "logs" / "latest.log",
            Path.home() / ".minecraft" / "logs" / "latest.log",
            # Badlion sometimes writes under .minecraft/logs/blclient/minecraft
            Path.home() / "AppData" / "Roaming" / ".minecraft" / "logs" / "blclient" / "minecraft" / "latest.log",
            # Lunar profiles (1.8)
            Path.home() / ".lunarclient" / "profiles" / "lunar" / "1.8" / "logs" / "latest.log",
        ]
    
    def find_log_file(self):
        """查找Minecraft日志文件（自动选择最近在写入的 latest.log）"""
        print("🔍 查找Minecraft日志文件...")
        candidates = []
        for p in self.default_paths:
            try:
                p = Path(p)  # ensure Path
            except Exception:
                continue
            # If a directory is provided, prefer latest.log, but also consider other active log files.
            # (Some launchers write chat lines to a different file name, and latest.log may not be the one
            # being actively appended.)
            if p.exists() and p.is_dir():
                p2 = p / "latest.log"
                if p2.exists():
                    candidates.append(p2)
                try:
                    # Consider other *.log files in the folder (e.g. 2026-01-24-1.log) and any
                    # launcher-specific files without extension.
                    for fp in list(p.glob("*.log")) + [x for x in p.iterdir() if x.is_file() and x.suffix == ""]:
                        if fp.exists() and fp.is_file():
                            candidates.append(fp)
                except Exception:
                    pass
                continue
            if p.exists():
                candidates.append(p)
        if not candidates:
            print("✗ 未找到默认路径的日志文件")
            return False
        # Pick the most recently modified candidate (best proxy for 'active' log)
        try:
            best = max(candidates, key=lambda x: x.stat().st_mtime)
        except Exception:
            best = candidates[0]
        self.log_file = str(best)
        print(f"✓ 选择日志文件: {self.log_file}")
        return True
    def start(self):
        if not self.log_file and not self.find_log_file():
            print("✗ 无法找到日志文件，无法启动监控")
            return False
        
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.thread.start()
            print("✓ 开始监控Minecraft日志...")
            return True
        return False
    
    def stop(self):
        if self.running:
            print("⏹️ 正在停止监控...")
            self.running = False
            if self.thread:
                self.thread.join(timeout=1)
            print("✗ 停止监控Minecraft日志")
    
    def _monitor_loop(self):
        """监控循环"""
        print("📊 进入监控循环...")
        try:
            with open(self.log_file, 'rb') as f:
                f.seek(0, os.SEEK_END)
                self.last_position = f.tell()
                print(f"?? ??????: {self.last_position}")
                while self.running:
                    try:
                        current_size = os.path.getsize(self.log_file)
                    except OSError:
                        time.sleep(1)
                        continue
                    if current_size < self.last_position:
                        print("?? ?????????????")
                        f.seek(0, os.SEEK_END)
                        self.last_position = f.tell()
                    elif current_size > self.last_position:
                        print(f"?? ??????: {current_size - self.last_position} ??")
                        f.seek(self.last_position)
                        data = f.read(current_size - self.last_position)
                        self.last_position = current_size
                        if data:
                            try:
                                new_content = data.decode('utf-8', errors='ignore')
                            except Exception:
                                new_content = ''
                            if new_content.strip():
                                self._process_content(new_content)
                    time.sleep(0.5)
                    
        except Exception as e:
            print(f"✗ 监控出错: {e}")
            import traceback
            traceback.print_exc()
    
    def _process_content(self, content):
        """处理新内容"""
        lines = content.strip().split('\n')
        
        for line in lines:
            if not line.strip():
                continue
            
            # 避免重复处理相同的消息
            line_hash = hash(line.strip())
            if line_hash in self.last_messages:
                continue
            
            self.last_messages.append(line_hash)
            if len(self.last_messages) > 100:  # 保持列表大小
                self.last_messages.pop(0)
            # 使用过滤器判断是否保留此消息（用于自动翻译/过滤显示）
            keep_for_translation = self.message_filter.should_keep(line)
            # 清理消息
            cleaned_message = self.message_filter.clean_message(line)
            
            # 判断消息类型
            if self.message_filter.is_system_message(cleaned_message):
                msg_type = "system"
                print(f"⚙️ 系统消息: {cleaned_message[:50]}...")
            else:
                # 尝试提取玩家信息
                player, message_content = self.message_filter.extract_player_message(cleaned_message)
                if player:
                    msg_type = "chat"
                    cleaned_message = f"<{player}> {message_content}"
                    print(f"🎮 玩家消息: {player}: {message_content[:50]}...")
                else:
                    msg_type = "info"
                    print(f"📝 信息消息: {cleaned_message[:50]}...")
            
            # 回调处理消息
            if self.callback:
                self.callback(cleaned_message, msg_type, raw_line=line, keep_for_translation=keep_for_translation)
# ==================== 主程序 ====================
class EnhancedMinecraftTranslator:
    def __init__(self):
        self.root = tk.Tk()
        
        # 初始化翻译器
        self.google_translator = GoogleTranslator()
        self.baidu_translator = None
        
        # 初始化语言检测器
        self.lang_detector = LanguageDetector()
        self.message_filter = MessageFilter()

        # Stats tracking
        self._stats = {
            'total': 0,
            'success': 0,
            'fail': 0,
            'cache_hit': 0,
            'total_ms': 0.0,
        }
        self._stats_by_engine = {}
        self._stats_window = None
        self._stats_vars = {}
        
        # 加载配置
        self.config = self.load_config()
        # 应用过滤选项（来自配置）
        self.message_filter.set_options(
            enabled=bool(self.config.get('filter_messages', True)),
            keep_system=bool(self.config.get('filter_keep_system', False)),
            keep_rewards=bool(self.config.get('filter_keep_rewards', False)),
        )
        
        # 初始化日志监控
        self.log_monitor = EnhancedMinecraftLogMonitor(self.on_log_message)
        
        # 用户手动指定的客户端日志文件（优先）
        try:
            bl = self.config.get("badlion_log_file")
            ln = self.config.get("lunar_log_file")
            if bl:
                self.log_monitor.default_paths.insert(0, Path(bl))
            if ln:
                self.log_monitor.default_paths.insert(0, Path(ln))
        except Exception:
            pass
# 让日志监控器也使用相同过滤设置
        try:
            self.log_monitor.message_filter.set_options(
                enabled=bool(self.config.get('filter_messages', True)),
                keep_system=bool(self.config.get('filter_keep_system', False)),
                keep_rewards=bool(self.config.get('filter_keep_rewards', False)),
            )
        except Exception:
            pass
        
        # 初始化变量
        # Auto-translate queue (avoid thread explosion)
        self._auto_translate_queue = queue.Queue()
        self._auto_translate_thread = threading.Thread(target=self._auto_translate_worker, daemon=True)
        self._auto_translate_thread.start()
        self._auto_last_msg = None
        self._auto_last_ts = 0.0
        self._auto_queue_limit = 5
        self.translations = []
        self.current_engine = "baidu"  # 默认使用百度翻译
        self.auto_detect_lang = True   # 默认启用语言自动检测
        
        # ????UI????????
        self._ui_ready = False
        try:
            self.root.after(1, self._deferred_ui_init)
        except Exception:
            self._deferred_ui_init()

    def _deferred_ui_init(self):
        """Defer heavy UI setup to keep startup responsive."""
        try:
            if getattr(self, '_ui_ready', False):
                return
            self.setup_ui()
            self._ui_ready = True
            # Initialize Baidu translator after UI is up
            if self.config.get('baidu_app_id') and self.config.get('baidu_secret_key'):
                self.baidu_translator = BaiduTranslator(
                    self.config['baidu_app_id'],
                    self.config['baidu_secret_key']
                )
                print("\u2713 \u5df2\u521d\u59cb\u5316\u767e\u5ea6\u7ffb\u8bd1\u5668")
            else:
                print("\u26a0\ufe0f \u767e\u5ea6\u7ffb\u8bd1\u5668\u672a\u914d\u7f6e")
        except Exception as e:
            try:
                print("\u2713 \u5df2\u521d\u59cb\u5316\u767e\u5ea6\u7ffb\u8bd1\u5668")
            except Exception:
                pass
    def load_config(self):
        """加载配置"""
        config_dir = Path.home() / ".minecraft_translator_enhanced"
        config_file = config_dir / "config.json"
        
        default_config = {
            'language': 'zh-CN',
            'auto_translate': True,
            'auto_detect': True,
            'filter_messages': True,
            'filter_keep_system': False,
            'filter_keep_rewards': False,
            'hide_all_messages': False,
            'no_translate_names': True,
            'save_path': str(Path.home() / "MinecraftTranslations"),
            'baidu_app_id': "",
            'baidu_secret_key': "",
            'overlay_opacity': 0.7,
            'overlay_geometry': '420x260+40+60',
            'license_server_url': 'https://xyxsb.shop',
            'mc_api_secret': ''
        }
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                # Merge: keep user values for known keys, preserve unknown keys too
                for key in default_config:
                    if key in user_config:
                        default_config[key] = user_config[key]
                for key, val in user_config.items():
                    if key not in default_config:
                        default_config[key] = val
                print("✓ 已加载配置文件")
            except Exception as e:
                print(f"✗ 加载配置文件失败: {e}")
        
        return default_config
    
    def save_config(self):
        """保存配置"""
        config_dir = Path.home() / ".minecraft_translator_enhanced"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        config_file = config_dir / "config.json"
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            print("✓ 已保存配置文件")
        except Exception as e:
            print(f"✗ 保存配置文件失败: {e}")
    
    def _stats_record(self, success: bool, duration_ms: float | None = None, cache_hit: bool = False, engine: str | None = None):
        try:
            self._stats['total'] += 1
            if cache_hit:
                self._stats['cache_hit'] += 1
            if success:
                self._stats['success'] += 1
            else:
                self._stats['fail'] += 1
            if duration_ms is not None:
                self._stats['total_ms'] += float(duration_ms)
        except Exception:
            pass

        # Per-engine stats
        try:
            key = (engine or 'unknown')
            st = self._stats_by_engine.get(key)
            if not st:
                st = {
                    'total': 0,
                    'success': 0,
                    'fail': 0,
                    'cache_hit': 0,
                    'total_ms': 0.0,
                }
                self._stats_by_engine[key] = st
            st['total'] += 1
            if cache_hit:
                st['cache_hit'] += 1
            if success:
                st['success'] += 1
            else:
                st['fail'] += 1
            if duration_ms is not None:
                st['total_ms'] += float(duration_ms)
        except Exception:
            pass

        self._refresh_stats_panel()

    def _stats_snapshot(self):
        try:
            total = int(self._stats.get('total', 0))
            success = int(self._stats.get('success', 0))
            fail = int(self._stats.get('fail', 0))
            cache_hit = int(self._stats.get('cache_hit', 0))
            total_ms = float(self._stats.get('total_ms', 0.0))
        except Exception:
            total = success = fail = cache_hit = 0
            total_ms = 0.0

        avg_ms = (total_ms / success) if success > 0 else 0.0
        hit_rate = (cache_hit / total) * 100.0 if total > 0 else 0.0
        fail_rate = (fail / total) * 100.0 if total > 0 else 0.0
        return {
            'total': total,
            'success': success,
            'fail': fail,
            'cache_hit': cache_hit,
            'avg_ms': avg_ms,
            'hit_rate': hit_rate,
            'fail_rate': fail_rate,
            'by_engine': dict(self._stats_by_engine),
        }

    def _refresh_stats_panel(self):
        try:
            if not self._stats_window or not self._stats_window.winfo_exists():
                return
            snap = self._stats_snapshot()
            self._stats_vars['total'].set(str(snap['total']))
            self._stats_vars['success'].set(str(snap['success']))
            self._stats_vars['fail'].set(str(snap['fail']))
            self._stats_vars['cache_hit'].set(str(snap['cache_hit']))
            self._stats_vars['hit_rate'].set(f"{snap['hit_rate']:.1f}%")
            self._stats_vars['avg_ms'].set(f"{snap['avg_ms']:.0f} ms")
            self._stats_vars['fail_rate'].set(f"{snap['fail_rate']:.1f}%")
        except Exception:
            pass

    def show_stats_panel(self):
        try:
            if self._stats_window and self._stats_window.winfo_exists():
                self._stats_window.deiconify()
                self._stats_window.lift()
                return
        except Exception:
            pass

        win = tk.Toplevel(self.root)
        win.title("翻译统计面板")
        win.geometry("420x260")
        self._stats_window = win

        container = ttk.Frame(win, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        items = [
            ("翻译总数", "total"),
            ("成功数", "success"),
            ("失败数", "fail"),
            ("缓存命中", "cache_hit"),
            ("命中率", "hit_rate"),
            ("平均耗时", "avg_ms"),
            ("失败率", "fail_rate"),
        ]

        for _, (label, key) in enumerate(items):
            row = ttk.Frame(container)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=label, width=12).pack(side=tk.LEFT)
            var = tk.StringVar(value="0")
            self._stats_vars[key] = var
            ttk.Label(row, textvariable=var).pack(side=tk.LEFT)

        btns = ttk.Frame(container)
        btns.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btns, text="刷新", command=self._refresh_stats_panel).pack(side=tk.LEFT)
        ttk.Button(btns, text="重置", command=self._reset_stats).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(btns, text="按引擎", command=self.show_engine_stats).pack(side=tk.LEFT, padx=(8, 0))

        self._refresh_stats_panel()

    def show_engine_stats(self):
        try:
            snap = self._stats_snapshot()
            by_engine = snap.get("by_engine", {}) or {}
        except Exception:
            by_engine = {}

        win = tk.Toplevel(self.root)
        win.title("按引擎统计")
        win.geometry("520x320")

        container = ttk.Frame(win, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(container)
        header.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(header, text="引擎", width=10).pack(side=tk.LEFT)
        ttk.Label(header, text="总数", width=8).pack(side=tk.LEFT)
        ttk.Label(header, text="成功", width=8).pack(side=tk.LEFT)
        ttk.Label(header, text="失败", width=8).pack(side=tk.LEFT)
        ttk.Label(header, text="命中率", width=10).pack(side=tk.LEFT)
        ttk.Label(header, text="平均耗时", width=10).pack(side=tk.LEFT)

        for eng, st in by_engine.items():
            total = int(st.get("total", 0))
            success = int(st.get("success", 0))
            fail = int(st.get("fail", 0))
            cache_hit = int(st.get("cache_hit", 0))
            total_ms = float(st.get("total_ms", 0.0))
            hit_rate = (cache_hit / total) * 100.0 if total > 0 else 0.0
            avg_ms = (total_ms / success) if success > 0 else 0.0

            row = ttk.Frame(container)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=str(eng), width=10).pack(side=tk.LEFT)
            ttk.Label(row, text=str(total), width=8).pack(side=tk.LEFT)
            ttk.Label(row, text=str(success), width=8).pack(side=tk.LEFT)
            ttk.Label(row, text=str(fail), width=8).pack(side=tk.LEFT)
            ttk.Label(row, text=f"{hit_rate:.1f}%", width=10).pack(side=tk.LEFT)
            ttk.Label(row, text=f"{avg_ms:.0f} ms", width=10).pack(side=tk.LEFT)


    def _reset_stats(self):
        try:
            self._stats = {
                'total': 0,
                'success': 0,
                'fail': 0,
                'cache_hit': 0,
                'total_ms': 0.0,
            }
            self._stats_by_engine = {}
        except Exception:
            pass
        self._refresh_stats_panel()

    def setup_ui(self):
        self.root.title("Minecraft智能翻译工具 v2.4")
        self.root.geometry("1000x800")
        
        # 创建菜单
        menubar = tk.Menu(self.root)
        self._menubar = menubar
        self.root.config(menu=menubar)
        # 显示控制：隐藏所有监控消息（菜单与主界面共用同一个变量）
        self.hide_all_var = tk.BooleanVar(value=self.config.get('hide_all_messages', False))
        # 名字不翻译：保留玩家名/前缀，仅翻译消息内容
        self.no_name_var = tk.BooleanVar(value=self.config.get('no_translate_names', True))
        
        # 这些变量在菜单与顶部控制栏共用（避免“菜单勾了但顶部不变/反之”）
        self.auto_var = tk.BooleanVar(value=self.config.get('auto_translate', True))
        self.detect_var = tk.BooleanVar(value=self.config.get('auto_detect', True))
        self.filter_var = tk.BooleanVar(value=self.config.get('filter_messages', True))
        self.keep_system_var = tk.BooleanVar(value=self.config.get('filter_keep_system', False))
        self.keep_rewards_var = tk.BooleanVar(value=self.config.get('filter_keep_rewards', False))
        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="保存当前翻译", command=self.save_current_translation)
        file_menu.add_command(label="导出历史记录", command=self.export_history)
        file_menu.add_command(label="设置保存路径", command=self.set_save_path)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        
        # 翻译菜单
        translate_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="翻译", menu=translate_menu)
        translate_menu.add_command(label="翻译当前文本", command=self.translate_text)
        translate_menu.add_command(label="智能翻译", command=self.smart_translate)
        translate_menu.add_command(label="网页翻译", command=self.web_translate)
        translate_menu.add_separator()
        translate_menu.add_command(label="清空所有", command=self.clear_all)
        
        # 工具菜单
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="工具", menu=tools_menu)
        tools_menu.add_command(label="API设置", command=self.show_api_settings)
        tools_menu.add_command(label="测试翻译API", command=self.test_translation_api)
        tools_menu.add_command(label="语言检测测试", command=self.test_language_detection)
        tools_menu.add_command(label="手动选择日志文件", command=self.manual_select_log)
        tools_menu.add_separator()
        tools_menu.add_command(label="选择Badlion日志文件", command=self.select_badlion_log)
        tools_menu.add_command(label="选择Lunar日志文件", command=self.select_lunar_log)
        tools_menu.add_command(label="查看日志格式", command=self.view_log_format)
        tools_menu.add_separator()
        tools_menu.add_command(label="统计面板", command=self.show_stats_panel)
        
        # 设置菜单
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="设置", menu=settings_menu)
        # 顶部控制栏（你截图那一排）统一放在「设置 → 顶部控制栏 → ...」里
        toolbar_menu = tk.Menu(settings_menu, tearoff=0)
        settings_menu.add_cascade(label="顶部控制栏", menu=toolbar_menu)
        # ── 翻译相关 ──
        toolbar_translate = tk.Menu(toolbar_menu, tearoff=0)
        toolbar_menu.add_cascade(label="翻译选项", menu=toolbar_translate)
        toolbar_translate.add_checkbutton(label="自动翻译", variable=self.auto_var, command=self.toggle_auto_translate)
        toolbar_translate.add_checkbutton(label="自动检测语言", variable=self.detect_var, command=self.toggle_auto_detect)
        toolbar_translate.add_checkbutton(label="名字不翻译", variable=self.no_name_var, command=self.toggle_no_translate_names)
        # ── 过滤/显示相关 ──
        # NOTE: 顶部那一排复选框已删除，所有开关统一在菜单里维护。
        toolbar_filter = tk.Menu(toolbar_menu, tearoff=0)
        self.toolbar_filter_menu = toolbar_filter
        toolbar_menu.add_cascade(label="过滤与显示", menu=toolbar_filter)
        toolbar_filter.add_checkbutton(label="过滤无用信息", variable=self.filter_var, command=self.toggle_message_filter)
        toolbar_filter.add_checkbutton(label="保留系统公告", variable=self.keep_system_var, command=self.toggle_filter_keep_system)
        self.toolbar_keep_system_idx = toolbar_filter.index("end")
        toolbar_filter.add_checkbutton(label="保留奖励提示", variable=self.keep_rewards_var, command=self.toggle_filter_keep_rewards)
        self.toolbar_keep_rewards_idx = toolbar_filter.index("end")
        toolbar_filter.add_separator()
        toolbar_filter.add_checkbutton(label="隐藏所有消息", variable=self.hide_all_var, command=self.toggle_hide_all_messages)
        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="管理员控制面板", command=self._open_admin_panel)
        help_menu.add_command(label="使用说明", command=self.show_help)
        help_menu.add_command(label="赞助", command=self.show_sponsor)
        help_menu.add_command(label="关于", command=self.show_about)
        
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 顶部控制栏
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 翻译引擎选择
        ttk.Label(control_frame, text="翻译引擎:").pack(side=tk.LEFT, padx=(0, 5))
        self.engine_var = tk.StringVar(value=self.config.get('translation_engine', 'baidu'))
        engine_combo = ttk.Combobox(control_frame, textvariable=self.engine_var,
                                   values=['baidu', 'google'], state='readonly', width=10)
        engine_combo.pack(side=tk.LEFT, padx=(0, 10))
        engine_combo.bind('<<ComboboxSelected>>', self.on_engine_change)
        
        # 目标语言
        ttk.Label(control_frame, text="目标语言:").pack(side=tk.LEFT, padx=(0, 5))
        self.lang_var = tk.StringVar(value=self.config.get('language', 'zh-CN'))
        lang_combo = ttk.Combobox(control_frame, textvariable=self.lang_var,
                                 values=['zh-CN', 'en', 'ja', 'ko', 'fr', 'de', 'es', 'ru'],
                                 state='readonly', width=10)
        lang_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        # 顶部那一排复选框已删除：相关开关全部在「设置 → 顶部控制栏」里。
        # 这里仅保留引擎/语言选择与监控控制。
        # 根据过滤开关启用/禁用菜单里的子选项
        self._update_filter_option_state()
        
        # 日志监控状态
        self.monitor_status = ttk.Label(control_frame, text="监控: 停止", foreground="red")
        self.monitor_status.pack(side=tk.LEFT, padx=(0, 10))
        
        # 监控控制按钮
        self.monitor_btn = ttk.Button(control_frame, text="启动监控",
                                     command=self.toggle_monitor, width=12)
        self.monitor_btn.pack(side=tk.LEFT)
        
        # 测试按钮
        ttk.Button(control_frame, text="测试监控", 
                  command=self.test_monitor, width=10).pack(side=tk.LEFT, padx=(10, 0))
        
        # 主内容区域
        content_paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        content_paned.pack(fill=tk.BOTH, expand=True)
        
        # 左侧面板
        left_frame = ttk.Frame(content_paned)
        content_paned.add(left_frame, weight=1)
        
        # 右侧面板
        right_frame = ttk.Frame(content_paned)
        content_paned.add(right_frame, weight=1)
        
        # ===== 左侧内容 =====
        # 输入区域
        input_frame = ttk.LabelFrame(left_frame, text="输入文本", padding="10")
        input_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.input_text = scrolledtext.ScrolledText(input_frame, height=8, wrap=tk.WORD)
        self.input_text.pack(fill=tk.BOTH, expand=True)
        
        # 输入按钮
        input_btns = ttk.Frame(input_frame)
        input_btns.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(input_btns, text="智能翻译", command=self.smart_translate,
                  width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(input_btns, text="普通翻译", command=self.translate_text,
                  width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(input_btns, text="清空", command=self.clear_input,
                  width=12).pack(side=tk.LEFT, padx=2)
        
        # 实时监控显示
        monitor_frame = ttk.LabelFrame(left_frame, text="实时监控 (过滤后)", padding="10")
        monitor_frame.pack(fill=tk.BOTH, expand=True)
        
        self.monitor_frame = monitor_frame  # 用于切换标题显示
        # 监控工具栏
        monitor_toolbar = ttk.Frame(monitor_frame)
        monitor_toolbar.pack(fill=tk.X, pady=(0, 6))
        self.monitor_show_all = False  # 仅影响监控显示（不影响自动翻译）
        self.monitor_buffer = []  # [(timestamp, message, msg_type)]
        self.monitor_buffer_limit = 2000
        self.show_all_logs_btn = ttk.Button(
            monitor_toolbar,
            text="显示全部日志",
            command=self.toggle_show_all_logs,
            width=14
        )
        self.show_all_logs_btn.pack(side=tk.LEFT, padx=2)
        self.monitor_text = scrolledtext.ScrolledText(monitor_frame, height=12, wrap=tk.WORD)
        self.monitor_text.pack(fill=tk.BOTH, expand=True)
        # Chat source tags
        try:
            self.monitor_text.tag_config('src_public', foreground='#2563eb')
            self.monitor_text.tag_config('src_team', foreground='#16a34a')
            self.monitor_text.tag_config('src_private', foreground='#db2777')
            self.monitor_text.tag_config('src_guild', foreground='#7c3aed')
            self.monitor_text.tag_config('src_system', foreground='#d97706')
        except Exception:
            pass
        
        # ===== 右侧内容 =====
        # 翻译结果
        result_frame = ttk.LabelFrame(right_frame, text="翻译结果", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.result_text = scrolledtext.ScrolledText(result_frame, height=15, wrap=tk.WORD)
        self.result_text.pack(fill=tk.BOTH, expand=True)
        
        # 结果按钮
        result_btns = ttk.Frame(result_frame)
        result_btns.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(result_btns, text="复制结果", command=self.copy_result,
                  width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(result_btns, text="保存", command=self.save_result,
                  width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(result_btns, text="详细分析", command=self.show_detailed_analysis,
                  width=10).pack(side=tk.LEFT, padx=2)
        
        # 翻译历史
        history_frame = ttk.LabelFrame(right_frame, text="最近翻译", padding="10")
        history_frame.pack(fill=tk.BOTH, expand=True)
        
        self.history_listbox = tk.Listbox(history_frame)
        self.history_listbox.pack(fill=tk.BOTH, expand=True)
        
        # 绑定双击事件
        self.history_listbox.bind('<Double-Button-1>', self.on_history_select)
        
        # 历史按钮
        history_btns = ttk.Frame(history_frame)
        history_btns.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(history_btns, text="查看详情", command=self.view_history_detail,
                  width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(history_btns, text="清空历史", command=self.clear_history_list,
                  width=10).pack(side=tk.LEFT, padx=2)
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪 | 等待输入...")
        status_bar = ttk.Label(self.root, textvariable=self.status_var,
                              relief=tk.SUNKEN, padding=(5, 2))
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # 右下角控制面板 + 悬浮窗
        try:
            self._init_corner_panel()
            self._init_overlay()
            self._refresh_license_status()
        except Exception:
            pass
        
        # 加载历史记录
        self.load_history()
        
        # 绑定快捷键
        self.root.bind('<Control-t>', lambda e: self.smart_translate())
        self.root.bind('<Control-w>', lambda e: self.web_translate())
        self.root.bind('<Control-s>', lambda e: self.save_current_translation())
        self.root.bind('<Control-d>', lambda e: self.test_language_detection())
        
        print("✓ UI设置完成")

    def _init_corner_panel(self):
        # 右下角按钮面板
        self._corner_panel = ttk.Frame(self.root)
        self._corner_panel.place(relx=1.0, rely=1.0, x=-12, y=-52, anchor="se")

        self.license_status_var = tk.StringVar(value="")
        ttk.Label(self._corner_panel, textvariable=self.license_status_var).pack(anchor="e", pady=(0, 6))

        self._pause_time_btn = ttk.Button(
            self._corner_panel,
            text="暂停时长",
            command=self._toggle_pause_time,
        )
        self._pause_time_btn.pack(anchor="e", fill="x", pady=(0, 6))

        self._overlay_toggle_btn = ttk.Button(
            self._corner_panel,
            text="悬浮窗开/关 (F8)",
            command=self._toggle_overlay,
        )
        self._overlay_toggle_btn.pack(anchor="e", fill="x", pady=(0, 6))

        self._activate_btn = ttk.Button(
            self._corner_panel,
            text="卡密激活/查看机器码",
            command=self._open_activation_dialog,
        )
        self._activate_btn.pack(anchor="e", fill="x", pady=(0, 6))

        self._force_sync_btn = ttk.Button(
            self._corner_panel,
            text="强制同步",
            command=self._force_sync_license,
        )
        self._force_sync_btn.pack(anchor="e", fill="x")

        # F8 绑定
        try:
            self.root.bind("<F8>", lambda e: self._toggle_overlay())
        except Exception:
            pass

    def _init_overlay(self):
        try:
            from ui.overlay import OverlayWindow
        except Exception:
            self.overlay = None
            return
        try:
            opacity = float(self.config.get("overlay_opacity", 0.7) or 0.7)
        except Exception:
            opacity = 0.7
        geom = self.config.get("overlay_geometry", None)
        self.overlay = OverlayWindow(
            self.root,
            opacity=opacity,
            initial_geometry=geom,
            on_geometry_change=self._save_overlay_geometry,
            translate_cb=self._overlay_translate_cb,
            config_get=lambda k, d=None: self.config.get(k, d),
        )

    def _toggle_overlay(self):
        try:
            if getattr(self, "overlay", None):
                self.overlay.toggle()
        except Exception:
            pass

    def _save_overlay_geometry(self, geom: str):
        try:
            self.config["overlay_geometry"] = geom
            self.save_config()
        except Exception:
            pass

    def _overlay_translate_cb(self, text, target_lang):
        """Overlay translate callback: return (ok, out, err)."""
        try:
            from license.state import can_consume, consume
        except Exception:
            can_consume = None
            consume = None
        cost = 0.5
        if can_consume and not can_consume(cost):
            return False, "", "未授权/请先激活卡密"
        if consume and not consume(cost):
            return False, "", "扣费失败/请检查余额"
        try:
            engine = self.current_engine
            if engine == "baidu" and self.baidu_translator:
                out, err = self.baidu_translator.translate(text, "auto", "zh")
            else:
                google_lang = "zh-CN" if target_lang in (None, "", "zh", "zh-CN") else target_lang
                out, err = self.google_translator.translate(text, "auto", google_lang)
            if err:
                return False, "", str(err)
            return True, out or "", None
        except Exception as e:
            return False, "", str(e)

    def _open_activation_dialog(self):
        try:
            from license.activate_ui import show_activation_dialog
            show_activation_dialog(self.root, on_change=self._refresh_license_status)
        except Exception as e:
            try:
                messagebox.showerror("错误", str(e))
            except Exception:
                pass

    def _refresh_license_status(self):
        try:
            from license.state import get_status, is_time_paused
        except Exception:
            return
        try:
            status, credits, perm, time_left = get_status()
            if perm:
                txt = f"授权：{status} | 金币: {credits:.1f} | 时长: 永久"
            else:
                days = time_left // 86400
                hours = (time_left % 86400) // 3600
                paused = " | 已暂停" if is_time_paused() else ""
                txt = f"授权：{status} | 金币: {credits:.1f} | 时长: {days}天{hours}小时{paused}"
            if hasattr(self, "license_status_var"):
                self.license_status_var.set(txt)
        except Exception:
            pass

    def _toggle_pause_time(self):
        try:
            from license.state import is_time_paused, pause_time, resume_time
            if is_time_paused():
                ok = resume_time()
                msg = "已恢复计时" if ok else "恢复失败"
            else:
                ok = pause_time()
                msg = "已暂停时长" if ok else "暂停失败"
            self.status_var.set(msg)
            self._refresh_license_status()
        except Exception:
            pass

    def _force_sync_license(self):
        try:
            from license.state import load_state, set_entitlement
            from license.online import verify_with_server
            from license.machine_id import get_machine_code
            st = load_state()
            token = st.get("session_token")
            if not token:
                messagebox.showinfo("提示", "请先激活卡密后再同步。")
                return
            resp = verify_with_server(token, get_machine_code())
            set_entitlement(
                int(resp.get("time_left", 0) or 0),
                float(resp.get("credits", 0.0) or 0.0),
                bool(resp.get("is_permanent", False)),
                token,
            )
            self._refresh_license_status()
            messagebox.showinfo("提示", "同步成功。")
        except Exception as e:
            try:
                messagebox.showerror("错误", str(e))
            except Exception:
                pass
    
    def toggle_auto_translate(self):
        """切换自动翻译"""
        self.config['auto_translate'] = self.auto_var.get()
        status = "开启" if self.auto_var.get() else "关闭"
        self.status_var.set(f"自动翻译已{status}")
        print(f"⚙️ 自动翻译: {status}")
    
    def toggle_auto_detect(self):
        """切换自动语言检测"""
        self.config['auto_detect'] = self.detect_var.get()
        status = "开启" if self.detect_var.get() else "关闭"
        self.status_var.set(f"自动语言检测已{status}")
        print(f"⚙️ 自动语言检测: {status}")
    
    def apply_filter_settings(self):
        """把 UI 过滤选项应用到过滤器与日志监控器。"""
        enabled = bool(self.filter_var.get()) if hasattr(self, 'filter_var') else bool(self.config.get('filter_messages', True))
        keep_system = bool(getattr(self, 'keep_system_var', None).get()) if hasattr(self, 'keep_system_var') else bool(self.config.get('filter_keep_system', False))
        keep_rewards = bool(getattr(self, 'keep_rewards_var', None).get()) if hasattr(self, 'keep_rewards_var') else bool(self.config.get('filter_keep_rewards', False))
        # 写入配置（便于下次启动保持一致）
        self.config['filter_messages'] = enabled
        self.config['filter_keep_system'] = keep_system
        self.config['filter_keep_rewards'] = keep_rewards
        # 应用到过滤器
        try:
            self.message_filter.set_options(enabled=enabled, keep_system=keep_system, keep_rewards=keep_rewards)
        except Exception:
            pass
        # 日志监控器也同步
        try:
            self.log_monitor.message_filter.set_options(enabled=enabled, keep_system=keep_system, keep_rewards=keep_rewards)
        except Exception:
            pass
        # 更新子选项可用状态
        self._update_filter_option_state()
    def _update_filter_option_state(self):
        """过滤开关关闭时，禁用菜单里的“保留系统公告/保留奖励提示”（避免误解）。"""
        try:
            enabled = bool(self.filter_var.get())
            state = "normal" if enabled else "disabled"
            # 旧版本：顶部控制栏有对应的 ttk.Checkbutton，这里会去 disable。
            # 新版本：顶部那一排已删除，仅通过菜单项控制，因此在菜单里禁用。
            if hasattr(self, "toolbar_filter_menu"):
                m = self.toolbar_filter_menu
                if hasattr(self, "toolbar_keep_system_idx"):
                    m.entryconfig(self.toolbar_keep_system_idx, state=state)
                if hasattr(self, "toolbar_keep_rewards_idx"):
                    m.entryconfig(self.toolbar_keep_rewards_idx, state=state)
        except Exception:
            # 禁用只是体验优化，不影响功能。
            pass
    def toggle_message_filter(self):
        """切换消息过滤"""
        status = "开启" if self.filter_var.get() else "关闭"
        self.status_var.set(f"消息过滤已{status}")
        print(f"⚙️ 消息过滤: {status}")
        self.apply_filter_settings()
        try:
            self.save_config()
        except Exception:
            pass
    def toggle_filter_keep_system(self):
        """切换：保留系统公告"""
        status = "开启" if self.keep_system_var.get() else "关闭"
        self.status_var.set(f"系统公告保留已{status}")
        print(f"⚙️ 系统公告保留: {status}")
        self.apply_filter_settings()
        try:
            self.save_config()
        except Exception:
            pass
    def toggle_filter_keep_rewards(self):
        """切换：保留奖励提示"""
        status = "开启" if self.keep_rewards_var.get() else "关闭"
        self.status_var.set(f"奖励提示保留已{status}")
        print(f"⚙️ 奖励提示保留: {status}")
        self.apply_filter_settings()
        try:
            self.save_config()
        except Exception:
            pass
    
    def toggle_no_translate_names(self):
        """切换：名字不翻译（保留玩家名/前缀，仅翻译消息内容）"""
        try:
            enabled = bool(self.no_name_var.get())
        except Exception:
            enabled = bool(self.config.get('no_translate_names', True))
        self.config['no_translate_names'] = enabled
        status = "开启" if enabled else "关闭"
        try:
            self.status_var.set(f"名字不翻译已{status}")
        except Exception:
            pass
        try:
            self.save_config()
        except Exception:
            pass
    def toggle_hide_all_messages(self):
        """切换：隐藏所有监控消息（不显示任何监控行，包括玩家聊天）"""
        try:
            hide_all = bool(self.hide_all_var.get())
        except Exception:
            hide_all = bool(self.config.get('hide_all_messages', False))
        self.config['hide_all_messages'] = hide_all
        try:
            self.save_config()
        except Exception:
            pass
        # 立即清空监控显示，避免残留
        try:
            if hide_all and hasattr(self, 'monitor_text'):
                self.monitor_text.delete('1.0', tk.END)
                self.status_var.set("已开启：隐藏所有监控消息（不显示任何消息）")
            elif hasattr(self, 'status_var'):
                self.status_var.set("已关闭：隐藏所有监控消息")
        except Exception:
            pass
        print(f"🕶️ 隐藏所有监控消息: {'开启' if hide_all else '关闭'}")
    def on_engine_change(self, event=None):
        """翻译引擎改变"""
        self.current_engine = self.engine_var.get()
        self.config['translation_engine'] = self.current_engine
        self.status_var.set(f"已切换到{self.current_engine}翻译引擎")
        print(f"✓ 切换到{self.current_engine}翻译引擎")
    def toggle_show_all_logs(self):
        """切换实时监控是否显示全部原始日志（仅影响显示，不影响自动翻译/扣费等）。"""
        self.monitor_show_all = not bool(getattr(self, 'monitor_show_all', False))
        if hasattr(self, 'show_all_logs_btn') and self.show_all_logs_btn:
            self.show_all_logs_btn.config(text=("恢复过滤显示" if self.monitor_show_all else "显示全部日志"))
        if hasattr(self, 'monitor_frame') and self.monitor_frame:
            self.monitor_frame.config(text=("实时监控 (全部)" if self.monitor_show_all else "实时监控 (过滤后)"))
        self._refresh_monitor_display()
    def _refresh_monitor_display(self):
        """根据当前开关刷新监控窗口显示。"""
        if not hasattr(self, 'monitor_text') or self.monitor_text is None:
            return
        hide_all = False
        try:
            hide_all = bool(self.hide_all_var.get())
        except Exception:
            hide_all = bool(self.config.get('hide_all_messages', False))
        self.monitor_text.delete("1.0", tk.END)
        buf = getattr(self, 'monitor_buffer', []) or []
        show_all = bool(getattr(self, 'monitor_show_all', False))
        for ts, msg, msg_type in buf:
            if show_all:
                self.monitor_text.insert(tk.END, f"[{ts}] {msg}\n")
            else:
                if hide_all:
                    continue
                if self.message_filter.should_keep(msg):
                    self.monitor_text.insert(tk.END, f"[{ts}] {msg}\n")
        self.monitor_text.see(tk.END)
    def _monitor_tag_for_msg_type(self, msg_type: str) -> str:
        if not msg_type:
            return ''
        m = str(msg_type).lower()
        if m == 'system' or 'system' in m:
            return 'src_system'
        if 'private' in m:
            return 'src_private'
        if 'team' in m:
            return 'src_team'
        if 'guild' in m:
            return 'src_guild'
        if 'public' in m:
            return 'src_public'
        return ''

    def on_log_message(self, message, msg_type, raw_line=None, keep_for_translation=None):
        """日志监控回调"""
        # Ensure UI updates happen on the Tk main thread
        if threading.current_thread() is not threading.main_thread():
            try:
                self.root.after(0, self.on_log_message, message, msg_type, raw_line, keep_for_translation)
                return
            except Exception:
                pass
        if keep_for_translation is None:
            try:
                keep_for_translation = self.message_filter.should_keep(raw_line or message)
            except Exception:
                keep_for_translation = True
        ts = time.strftime("%H:%M:%S")
        try:
            self.monitor_buffer.append((ts, message, msg_type))
            limit = int(getattr(self, 'monitor_buffer_limit', 2000))
            if len(self.monitor_buffer) > limit:
                self.monitor_buffer = self.monitor_buffer[-limit:]
        except Exception:
            pass
        hide_all = False
        try:
            hide_all = bool(self.hide_all_var.get())
        except Exception:
            hide_all = bool(self.config.get('hide_all_messages', False))
        if bool(getattr(self, 'monitor_show_all', False)):
            display_line = (raw_line if raw_line is not None else message)
            self.monitor_text.insert(tk.END, f"[{ts}] {display_line}\n")
            self.monitor_text.see(tk.END)
        else:
            if (not hide_all) and keep_for_translation:
                self.monitor_text.insert(tk.END, f"[{ts}] {message}\n")
                self.monitor_text.see(tk.END)
        if keep_for_translation and self.auto_var.get():
            getattr(self, '_auto_translate_logic', self._auto_translate_message)(message, msg_type)
    def _auto_translate_worker(self):
        while True:
            item = self._auto_translate_queue.get()
            if item is None:
                return
            try:
                self._do_smart_translate(
                    item.get('text', ''),
                    item.get('detected_lang', Language.UNKNOWN),
                    target_lang=item.get('target_lang'),
                    engine=item.get('engine'),
                    auto=True,
                )
            except Exception:
                pass
            finally:
                try:
                    self._auto_translate_queue.task_done()
                except Exception:
                    pass
    def _auto_translate_message(self, message, msg_type):
        """??????"""
        detected_lang = self.lang_detector.detect(message)
        target_lang = self.lang_var.get()
        target_lang_simple = target_lang.replace('-CN', '') if '-CN' in target_lang else target_lang
        # Log auto-translate for visibility (chat only)
        try:
            if str(msg_type or '').lower() == 'chat':
                print(f"?? ????: '{message[:80]}'")
        except Exception:
            pass
        # Skip same-language only for non-chat messages
        if self.detect_var.get():
            if (detected_lang.value == target_lang_simple or
                (detected_lang == Language.CHINESE and target_lang_simple == 'zh')):
                if msg_type != "chat":
                    print(f"?? ?????? (???: {detected_lang.value}, ????: {target_lang_simple})")
                    return
        # Update input box on UI thread for visibility
        try:
            self.input_text.delete(1.0, tk.END)
            self.input_text.insert(1.0, message)
        except Exception:
            pass
        # Debounce + bounded queue to avoid thread explosion
        try:
            now = time.time()
            if message == getattr(self, '_auto_last_msg', None) and (now - getattr(self, '_auto_last_ts', 0.0)) < 1.0:
                return
            self._auto_last_msg = message
            self._auto_last_ts = now
            if self._auto_translate_queue.qsize() >= int(getattr(self, '_auto_queue_limit', 5)):
                return
        except Exception:
            pass
        try:
            self._auto_translate_queue.put({
                'text': message,
                'detected_lang': detected_lang,
                'target_lang': target_lang,
                'engine': getattr(self, 'current_engine', 'baidu'),
            })
            # Track auto-translate source so UI can show translated lines in monitor
            try:
                pending = getattr(self, '_auto_pending', None)
                if pending is None:
                    pending = set()
                    setattr(self, '_auto_pending', pending)
                pending.add(message)
            except Exception:
                pass
        except Exception:
            pass
    def toggle_monitor(self):
        """切换监控状态"""
        if not self.log_monitor.log_file:
            if not self.log_monitor.find_log_file():
                result = messagebox.askyesno("未找到日志", 
                    "未找到Minecraft日志文件\n"
                    "是否手动选择日志文件？")
                
                if result:
                    self.manual_select_log()
                    if not self.log_monitor.log_file:
                        return
                else:
                    return
        
        if self.log_monitor.running:
            self.log_monitor.stop()
            # 停止监控时，清空悬浮窗（显示翻译 + 输入翻译）
            try:
                if getattr(self, "overlay", None):
                    if hasattr(self.overlay, "clear_all"):
                        self.overlay.clear_all()
                    else:
                        try:
                            self.overlay.clear_display()
                            self.overlay.clear_input()
                        except Exception:
                            pass
            except Exception:
                pass
            self.monitor_btn.config(text="启动监控")
            self.monitor_status.config(text="监控: 停止", foreground="red")
            self.status_var.set("日志监控已停止")
            print("⏹️ 监控已停止")
        else:
            if self.log_monitor.start():
                self.monitor_btn.config(text="停止监控")
                self.monitor_status.config(text="监控: 运行中", foreground="green")
                self.status_var.set("开始监控Minecraft日志")
                print("▶️ 监控已启动")
            else:
                messagebox.showerror("错误", "无法启动日志监控")
                print("✗ 启动监控失败")
    
    def _tail_lines(self, file_path, max_lines=50, max_bytes=65536):
        try:
            with open(file_path, 'rb') as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                read_size = min(max_bytes, size)
                f.seek(max(size - read_size, 0), os.SEEK_SET)
                data = f.read(read_size)
            text = data.decode('utf-8', errors='ignore')
            lines = text.splitlines()
            return lines[-max_lines:] if max_lines else lines
        except Exception:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.readlines()[-max_lines:]
            except Exception:
                return []
    def test_monitor(self):
        """??????"""
        print("?? ????????...")
        
        if not self.log_monitor.find_log_file():
            messagebox.showwarning("??", "???Minecraft????")
            return
        
        # ??????
        messagebox.showinfo("????", f"??????:\n{self.log_monitor.log_file}")
        
        # ????????
        try:
            lines = self._tail_lines(self.log_monitor.log_file, max_lines=50)
            print(f"?? ????: {len(lines)}")
            
            # ??????
            filtered_count = 0
            for line in lines:
                if self.message_filter.should_keep(line):
                    filtered_count += 1
            
            self.status_var.set(f"?????? | ?????: {filtered_count}/50 ?")
            
            # ??????
            messagebox.showinfo("????", 
                f"????: {self.log_monitor.log_file}\n"
                f"????: {len(lines)}\n"
                f"??50??????: {filtered_count}?\n"
                f"????: {(1 - filtered_count/50)*100:.1f}%\n\n"
                "??????????????????")
            
        except Exception as e:
            messagebox.showerror("??", f"??????: {str(e)}")
            print(f"? ??????: {e}")
    def _select_client_log(self, client_name: str, default_dir: str, config_key: str):
        """选择指定客户端的日志文件（保存到配置，并优先用于自动查找）。"""
        try:
            initial = self.config.get(config_key) or default_dir
            file_path = filedialog.askopenfilename(
                title=f"选择{client_name}日志文件（建议 latest.log）",
                initialdir=initial,
                filetypes=[("日志文件", "*.log"), ("所有文件", "*.*")]
            )
            if not file_path:
                return False
            self.config[config_key] = file_path
            try:
                self.save_config()
            except Exception:
                pass
            # 更新监控器：把用户选择的文件放到候选路径最前
            try:
                if hasattr(self.log_monitor, "default_paths"):
                    # 先移除同名
                    self.log_monitor.default_paths = [p for p in self.log_monitor.default_paths if str(p) != str(file_path)]
                    self.log_monitor.default_paths.insert(0, Path(file_path))
                self.log_monitor.log_file = file_path
            except Exception:
                pass
            self.status_var.set(f"已选择{client_name}日志: {Path(file_path).name}")
            messagebox.showinfo("成功", f"已选择{client_name}日志文件:\n{file_path}")
            print(f"✓ 选择{client_name}日志文件: {file_path}")
            return True
        except Exception as e:
            messagebox.showerror("错误", f"选择日志失败：{e}")
            return False
    def select_badlion_log(self):
        """选择 Badlion 客户端日志文件"""
        default_dir = str(Path.home() / "AppData" / "Roaming" / ".minecraft" / "logs" / "blclient" / "minecraft")
        return self._select_client_log("Badlion", default_dir, "badlion_log_file")
    def select_lunar_log(self):
        """选择 Lunar 客户端日志文件"""
        default_dir = str(Path.home() / ".lunarclient" / "profiles" / "lunar" / "1.8" / "logs")
        return self._select_client_log("Lunar", default_dir, "lunar_log_file")
    def manual_select_log(self):
        """手动选择日志文件"""
        file_path = filedialog.askopenfilename(
            title="选择Minecraft日志文件",
            filetypes=[("日志文件", "*.log"), ("所有文件", "*.*")]
        )
        
        if file_path:
            self.log_monitor.log_file = file_path
            self.status_var.set(f"已选择日志文件: {Path(file_path).name}")
            messagebox.showinfo("成功", f"已选择日志文件:\n{file_path}")
            print(f"✓ 手动选择日志文件: {file_path}")
            return True
        return False
    
    def view_log_format(self):
        """查看日志格式"""
        if not self.log_monitor.find_log_file():
            messagebox.showwarning("错误", "未找到日志文件")
            return
        
        try:
            lines = self._tail_lines(self.log_monitor.log_file, max_lines=50)
            
            # 创建格式分析窗口
            format_win = tk.Toplevel(self.root)
            format_win.title("日志格式分析")
            format_win.geometry("800x600")
            
            notebook = ttk.Notebook(format_win)
            notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # 原始日志标签页
            raw_frame = ttk.Frame(notebook)
            notebook.add(raw_frame, text="原始日志")
            
            raw_text = scrolledtext.ScrolledText(raw_frame, wrap=tk.WORD)
            raw_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            raw_text.insert(tk.END, "".join(lines))
            
            # 过滤结果标签页
            filter_frame = ttk.Frame(notebook)
            notebook.add(filter_frame, text="过滤结果")
            
            filter_text = scrolledtext.ScrolledText(filter_frame, wrap=tk.WORD)
            filter_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            filter_result = "过滤分析报告\n"
            filter_result += "="*60 + "\n\n"
            
            total_lines = len(lines)
            kept_lines = 0
            
            for line in lines:
                if self.message_filter.should_keep(line):
                    kept_lines += 1
                    filter_result += f"✅ 保留: {line.strip()}\n"
                else:
                    filter_result += f"🚫 过滤: {line.strip()}\n"
            
            filter_result += f"\n过滤统计: 保留 {kept_lines}/{total_lines} 条 ({kept_lines/total_lines*100:.1f}%)\n"
            filter_text.insert(tk.END, filter_result)
            
            # 语言检测标签页
            lang_frame = ttk.Frame(notebook)
            notebook.add(lang_frame, text="语言检测")
            
            lang_text = scrolledtext.ScrolledText(lang_frame, wrap=tk.WORD)
            lang_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            lang_result = "语言检测报告\n"
            lang_result += "="*60 + "\n\n"
            
            lang_stats = {}
            for line in lines:
                clean_line = self.message_filter.clean_message(line.strip())
                if clean_line and len(clean_line) > 3:
                    lang = self.lang_detector.detect(clean_line)
                    lang_name = lang.value
                    lang_stats[lang_name] = lang_stats.get(lang_name, 0) + 1
                    lang_result += f"{lang_name.upper():8} | {clean_line[:60]}\n"
            
            lang_result += f"\n语言分布:\n"
            for lang_name, count in lang_stats.items():
                percentage = count/len(lines)*100
                lang_result += f"{lang_name.upper():8}: {count} 条 ({percentage:.1f}%)\n"
            
            lang_text.insert(tk.END, lang_result)
            
        except Exception as e:
            messagebox.showerror("错误", f"分析日志失败: {str(e)}")
    
    def smart_translate(self):
        """智能翻译：自动检测语言并翻译"""
        text = self.input_text.get(1.0, tk.END).strip()
        if not text:
            messagebox.showwarning("提示", "请输入要翻译的文本")
            return
        
        print(f"🧠 开始智能翻译: '{text}'")
        
        # 自动检测语言
        detected_lang = self.lang_detector.detect(text)
        print(f"🌐 检测到语言: {detected_lang.value}")
        
        # 显示语言检测结果
        self.status_var.set(f"检测到语言: {detected_lang.value} | 翻译中...")
        self.root.update()
        
        # 在新线程中翻译
        threading.Thread(target=self._do_smart_translate, args=(text, detected_lang), daemon=True).start()
    
    def _do_smart_translate(self, text, detected_lang, target_lang=None, engine=None):
        """执行智能翻译"""
        try:
            start_ts = time.time()
            if target_lang is None:
                target_lang = self.lang_var.get()
            if engine is None:
                engine = self.current_engine
            
            # 检查是否需要翻译
            target_lang_simple = target_lang.replace('-CN', '') if '-CN' in target_lang else target_lang
            if (detected_lang.value == target_lang_simple or 
                (detected_lang == Language.CHINESE and target_lang_simple == 'zh')):
                print(f"🌐 无需翻译，源语言和目标语言相同")
                self.root.after(0, self._update_translation_result, text, text, None, "智能翻译", detected_lang.value, target_lang, start_ts, False)
                return
            
            if engine == "baidu" and self.baidu_translator:
                # 使用百度翻译
                print("🚀 使用百度翻译...")
                from_lang = detected_lang.value if detected_lang != Language.UNKNOWN else 'auto'
                result, error = self.baidu_translator.translate(text, from_lang, 'zh')
                engine_name = "百度翻译"
            else:
                # 使用Google翻译
                print("🚀 使用Google翻译...")
                lang_map = {'zh-CN': 'zh-CN', 'en': 'en', 'ja': 'ja', 'ko': 'ko'}
                google_lang = lang_map.get(target_lang, 'zh-CN')
                from_lang = detected_lang.value if detected_lang != Language.UNKNOWN else 'auto'
                result, error = self.google_translator.translate(text, from_lang, google_lang)
                engine_name = "Google翻译"
            
            # 在主线程中更新UI
            self.root.after(0, self._update_translation_result, text, result, error, engine_name, detected_lang.value, target_lang, start_ts, False)
            
        except Exception as e:
            print(f"💥 翻译异常: {e}")
            import traceback
            traceback.print_exc()
            self.root.after(0, self._update_translation_result, text, None, str(e), "智能翻译", detected_lang.value, target_lang, start_ts, False)
    
    def translate_text(self):
        """普通翻译"""
        text = self.input_text.get(1.0, tk.END).strip()
        if not text:
            messagebox.showwarning("提示", "请输入要翻译的文本")
            return
        
        print(f"🔤 开始普通翻译: '{text}'")
        self.status_var.set("翻译中...")
        self.root.update()
        
        # 在新线程中翻译
        threading.Thread(target=self._do_translate, args=(text,), daemon=True).start()
    
    def _do_translate(self, text):
        """Translate (normal)."""
        try:
            start_ts = time.time()
            target_lang = self.lang_var.get()
            engine = self.current_engine
            print(f"Target language: {target_lang}")

            if engine == "baidu" and self.baidu_translator:
                print("Using Baidu...")
                result, error = self.baidu_translator.translate(text, "auto", "zh")
                engine_name = "Baidu"
            else:
                print("Using Google...")
                lang_map = {"zh-CN": "zh-CN", "en": "en", "ja": "ja", "ko": "ko"}
                google_lang = lang_map.get(target_lang, "zh-CN")
                result, error = self.google_translator.translate(text, "auto", google_lang)
                engine_name = "Google"

            self.root.after(0, self._update_translation_result, text, result, error, engine_name, "auto", target_lang, start_ts, False)

        except Exception as e:
            print(f"Translate error: {e}")
            import traceback
            traceback.print_exc()
            self.root.after(0, self._update_translation_result, text, None, str(e), "Translate", "unknown", target_lang, start_ts, False)


    def _update_translation_result(self, original, translated, error, engine_name, from_lang, to_lang, start_ts=None, cache_hit=False):
        """Update translation result in UI."""
        try:
            duration_ms = None
            if start_ts is not None and not cache_hit:
                duration_ms = max(0.0, (time.time() - float(start_ts)) * 1000.0)
            self._stats_record(success=(error is None), duration_ms=duration_ms, cache_hit=bool(cache_hit), engine=str(engine_name))
        except Exception:
            pass
        if error:
            result_text = f"[{engine_name} Error]\n"
            result_text += f"From: {from_lang} -> To: {to_lang}\n"
            result_text += f"Error: {error}\n"
            result_text += "=" * 50 + "\n"
            result_text += f"Original: {original}\n"

            self.status_var.set(f"Translate failed: {error}")
        else:
            result_text = f"[{engine_name} Result]\n"
            result_text += f"From: {from_lang} -> To: {to_lang}\n"
            result_text += "=" * 50 + "\n"
            result_text += f"Original: {original}\n"
            result_text += "-" * 50 + "\n"
            result_text += f"Translated: {translated}\n"

            self.status_var.set(f"Translate done - {len(original)} chars")

            # Save to history
            self.save_to_history(original, translated, engine_name, from_lang, to_lang)

        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(1.0, result_text)


    def test_language_detection(self):
        """测试语言检测"""
        test_text = self.input_text.get(1.0, tk.END).strip()
        if not test_text:
            test_text = "Hello World 你好世界 こんにちは世界 안녕하세요 세계"
        
        print(f"🧪 测试语言检测: '{test_text}'")
        
        lines = test_text.split('\n')
        results = []
        
        for line in lines:
            if line.strip():
                detected = self.lang_detector.detect(line)
                should_trans = self.lang_detector.should_translate(line, self.lang_var.get())
                results.append(f"文本: {line[:50]}...")
                results.append(f"检测语言: {detected.value}")
                results.append(f"需要翻译: {'是' if should_trans else '否'}")
                results.append("-" * 40)
        
        result_text = "语言检测测试结果\n"
        result_text += "=" * 50 + "\n\n"
        result_text += "\n".join(results)
        
        # 显示结果
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(1.0, result_text)
        
        self.status_var.set("语言检测测试完成")
        print("🧪 语言检测测试完成")
    
    def show_detailed_analysis(self):
        """显示详细分析"""
        text = self.input_text.get(1.0, tk.END).strip()
        if not text:
            messagebox.showwarning("提示", "请输入要分析的文本")
            return
        
        # 创建分析窗口
        analysis_win = tk.Toplevel(self.root)
        analysis_win.title("文本详细分析")
        analysis_win.geometry("700x500")
        
        notebook = ttk.Notebook(analysis_win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 语言分析标签页
        lang_frame = ttk.Frame(notebook)
        notebook.add(lang_frame, text="语言分析")
        
        lang_text = scrolledtext.ScrolledText(lang_frame, wrap=tk.WORD)
        lang_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 执行语言分析
        detected_lang = self.lang_detector.detect(text)
        should_trans = self.lang_detector.should_translate(text, self.lang_var.get())
        
        analysis_result = "文本语言详细分析\n"
        analysis_result += "=" * 60 + "\n\n"
        analysis_result += f"文本长度: {len(text)} 字符\n"
        analysis_result += f"检测语言: {detected_lang.value}\n"
        analysis_result += f"目标语言: {self.lang_var.get()}\n"
        analysis_result += f"需要翻译: {'是' if should_trans else '否'}\n"
        analysis_result += "\n文本内容:\n"
        analysis_result += "-" * 40 + "\n"
        analysis_result += text + "\n"
        analysis_result += "-" * 40 + "\n"
        
        # 字符统计
        chinese_count = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_count = len(re.findall(r'[A-Za-z]', text))
        digit_count = len(re.findall(r'[0-9]', text))
        other_count = len(text) - chinese_count - english_count - digit_count
        
        analysis_result += f"\n字符统计:\n"
        analysis_result += f"中文字符: {chinese_count}\n"
        analysis_result += f"英文字符: {english_count}\n"
        analysis_result += f"数字字符: {digit_count}\n"
        analysis_result += f"其他字符: {other_count}\n"
        
        lang_text.insert(tk.END, analysis_result)
        
        # 过滤分析标签页
        filter_frame = ttk.Frame(notebook)
        notebook.add(filter_frame, text="过滤分析")
        
        filter_text = scrolledtext.ScrolledText(filter_frame, wrap=tk.WORD)
        filter_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        filter_result = "消息过滤分析\n"
        filter_result += "=" * 60 + "\n\n"
        
        should_keep = self.message_filter.should_keep(text)
        filter_result += f"是否保留: {'是' if should_keep else '否'}\n\n"
        
        # 检查各个过滤模式
        filter_result += "过滤模式匹配:\n"
        for pattern in self.message_filter.filter_patterns[:10]:  # 只显示前10个
            if re.search(pattern, text, re.IGNORECASE):
                filter_result += f"🚫 匹配过滤模式: {pattern}\n"
        
        filter_result += "\n保留模式匹配:\n"
        for pattern in self.message_filter.keep_patterns[:10]:  # 只显示前10个
            if re.search(pattern, text, re.IGNORECASE):
                filter_result += f"✅ 匹配保留模式: {pattern}\n"
        
        filter_text.insert(tk.END, filter_result)
        
        # 玩家信息提取标签页
        player_frame = ttk.Frame(notebook)
        notebook.add(player_frame, text="玩家信息")
        
        player_text = scrolledtext.ScrolledText(player_frame, wrap=tk.WORD)
        player_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        player_result = "玩家信息提取\n"
        player_result += "=" * 60 + "\n\n"
        
        player, message = self.message_filter.extract_player_message(text)
        if player:
            player_result += f"提取到玩家名: {player}\n"
            player_result += f"提取到消息内容: {message}\n\n"
            
            # 清理后的玩家名
            cleaned_player = re.sub(r'^[a-zA-Z0-9]\[.*?\]\s*', '', player)
            cleaned_player = re.sub(r'^\d+\[\d+\?\].*?\]\s*', '', cleaned_player)
            
            if cleaned_player != player:
                player_result += f"清理后玩家名: {cleaned_player}\n"
        else:
            player_result += "未提取到玩家信息\n"
        
        player_text.insert(tk.END, player_result)
    
    def web_translate(self):
        """网页翻译"""
        text = self.input_text.get(1.0, tk.END).strip()
        if not text:
            messagebox.showwarning("提示", "请输入要翻译的文本")
            return
        
        try:
            encoded_text = urllib.parse.quote(text)
            if target_lang is None:
                target_lang = self.lang_var.get()
            if engine is None:
                engine = self.current_engine
            
            url = f"https://translate.google.com/?sl=auto&tl={target_lang}&text={encoded_text}&op=translate"
            webbrowser.open(url)
            
            self.status_var.set("已打开网页翻译")
            print(f"🌐 打开网页翻译: {url}")
            
        except Exception as e:
            messagebox.showerror("错误", f"无法打开网页: {str(e)}")
            print(f"🌐 打开网页翻译失败: {e}")
    
    def set_save_path(self):
        """设置保存路径"""
        folder_path = filedialog.askdirectory(
            title="选择翻译保存目录",
            initialdir=self.config.get('save_path', Path.home())
        )
        
        if folder_path:
            self.config['save_path'] = folder_path
            self.save_config()
            self.status_var.set(f"保存路径已设置为: {folder_path}")
            messagebox.showinfo("成功", f"保存路径已设置为:\n{folder_path}")
            print(f"📁 保存路径设置为: {folder_path}")
    
    def save_current_translation(self):
        """保存当前翻译"""
        text = self.input_text.get(1.0, tk.END).strip()
        result = self.result_text.get(1.0, tk.END).strip()
        
        if not text and not result:
            messagebox.showwarning("提示", "没有内容可保存")
            return
        
        save_dir = Path(self.config.get('save_path', Path.home() / "MinecraftTranslations"))
        save_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = save_dir / f"translation_{timestamp}.txt"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"Minecraft翻译记录\n")
                f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"引擎: {self.engine_var.get()}\n")
                f.write(f"目标语言: {self.lang_var.get()}\n")
                f.write("=" * 50 + "\n\n")
                
                if text:
                    f.write(f"原文:\n{text}\n\n")
                
                if result:
                    f.write(f"翻译:\n{result}\n\n")
                
                f.write("=" * 50 + "\n")
            
            messagebox.showinfo("成功", f"已保存到:\n{filename}")
            self.status_var.set(f"已保存: {filename.name}")
            print(f"💾 保存翻译到: {filename}")
            
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {str(e)}")
            print(f"💾 保存失败: {e}")
    
    def save_to_history(self, original, translated, engine, from_lang, to_lang):
        """保存到历史记录"""
        entry = {
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'original': original,
            'translated': translated,
            'engine': engine,
            'from_lang': from_lang,
            'to_lang': to_lang
        }
        
        self.translations.append(entry)
        
        # 更新历史列表显示
        self.update_history_list()
        
        # 保存到文件
        self.save_history_to_file()
        
        print(f"📝 添加到历史记录: {original[:30]}...")
    
    def update_history_list(self):
        """更新历史列表显示"""
        self.history_listbox.delete(0, tk.END)
        
        for i, trans in enumerate(reversed(self.translations[-20:]), 1):
            lang_info = f"{trans['from_lang']}→{trans['to_lang']}"
            display = f"{trans['time']} [{lang_info}] {trans['original'][:40]}..."
            self.history_listbox.insert(tk.END, display)
    
    def save_history_to_file(self):
        """保存历史记录到文件"""
        history_file = Path(self.config.get('save_path')) / "history.json"
        history_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self.translations[-100:], f, ensure_ascii=False, indent=2)
            print(f"📖 保存历史记录到: {history_file}")
        except Exception as e:
            print(f"📖 保存历史记录失败: {e}")
    
    def load_history(self):
        """加载历史记录"""
        history_file = Path(self.config.get('save_path')) / "history.json"
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    self.translations = json.load(f)
                self.update_history_list()
                print(f"📖 加载历史记录: {len(self.translations)} 条")
            except Exception as e:
                print(f"📖 加载历史记录失败: {e}")
                self.translations = []
        else:
            self.translations = []
            print("📖 历史记录文件不存在")
    
    def on_history_select(self, event):
        """选择历史记录"""
        selection = self.history_listbox.curselection()
        if selection:
            index = selection[0]
            # 由于列表是倒序显示，需要计算实际索引
            actual_index = len(self.translations) - 1 - index
            
            if 0 <= actual_index < len(self.translations):
                trans = self.translations[actual_index]
                self.input_text.delete(1.0, tk.END)
                self.input_text.insert(1.0, trans['original'])
                self.result_text.delete(1.0, tk.END)
                self.result_text.insert(1.0, trans['translated'])
                self.status_var.set(f"已加载历史记录 {trans['time']}")
                print(f"📖 加载历史记录: {trans['time']}")
    
    def view_history_detail(self):
        """查看历史记录详情"""
        selection = self.history_listbox.curselection()
        if not selection:
            messagebox.showwarning("提示", "请选择一条历史记录")
            return
        
        index = selection[0]
        actual_index = len(self.translations) - 1 - index
        
        if 0 <= actual_index < len(self.translations):
            trans = self.translations[actual_index]
            
            detail_win = tk.Toplevel(self.root)
            detail_win.title(f"翻译详情 - {trans['time']}")
            detail_win.geometry("600x400")
            
            text_widget = scrolledtext.ScrolledText(detail_win, wrap=tk.WORD)
            text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            content = f"时间: {trans['time']}\n"
            content += f"引擎: {trans['engine']}\n"
            content += f"语言: {trans['from_lang']} → {trans['to_lang']}\n"
            content += "=" * 50 + "\n\n"
            content += f"原文:\n{trans['original']}\n\n"
            content += "=" * 50 + "\n\n"
            content += f"翻译:\n{trans['translated']}\n"
            
            text_widget.insert(tk.END, content)
            text_widget.config(state=tk.DISABLED)
    
    def export_history(self):
        """导出历史记录"""
        if not self.translations:
            messagebox.showinfo("提示", "没有历史记录")
            return
        
        export_file = filedialog.asksaveasfilename(
            title="导出历史记录",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialdir=self.config.get('save_path', Path.home())
        )
        
        if export_file:
            try:
                with open(export_file, 'w', encoding='utf-8') as f:
                    f.write("Minecraft翻译历史记录\n")
                    f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"记录数量: {len(self.translations)}\n")
                    f.write("=" * 60 + "\n\n")
                    
                    for i, trans in enumerate(self.translations, 1):
                        f.write(f"记录 #{i}\n")
                        f.write(f"时间: {trans['time']}\n")
                        f.write(f"引擎: {trans['engine']}\n")
                        f.write(f"语言: {trans['from_lang']} → {trans['to_lang']}\n")
                        f.write("-" * 40 + "\n")
                        f.write(f"原文:\n{trans['original']}\n\n")
                        f.write(f"翻译:\n{trans['translated']}\n")
                        f.write("=" * 60 + "\n\n")
                
                messagebox.showinfo("成功", f"已导出 {len(self.translations)} 条记录")
                self.status_var.set(f"已导出到: {Path(export_file).name}")
                print(f"📤 导出历史记录到: {export_file}")
                
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {str(e)}")
                print(f"📤 导出失败: {e}")
    
    def clear_input(self):
        """清空输入"""
        self.input_text.delete(1.0, tk.END)
        self.result_text.delete(1.0, tk.END)
        self.status_var.set("已清空输入")
        print("🧹 清空输入")
    
    def clear_all(self):
        """清空所有"""
        self.clear_input()
        self.monitor_text.delete(1.0, tk.END)
        self.status_var.set("已清空所有内容")
        print("🧹 清空所有")
    
    def clear_history_list(self):
        """清空历史记录"""
        if messagebox.askyesno("确认", "确定要清空所有历史记录吗？"):
            self.translations = []
            self.update_history_list()
            self.save_history_to_file()
            self.status_var.set("历史记录已清空")
            print("🗑️ 清空历史记录")
    
    def copy_result(self):
        """复制结果"""
        result = self.result_text.get(1.0, tk.END).strip()
        if result:
            self.root.clipboard_clear()
            self.root.clipboard_append(result)
            self.status_var.set("已复制翻译结果")
            print("📋 复制翻译结果")
        else:
            messagebox.showwarning("提示", "没有翻译结果可复制")
    
    def save_result(self):
        """保存结果"""
        self.save_current_translation()
    
    def show_api_settings(self):
        """显示API设置窗口"""
        settings_win = tk.Toplevel(self.root)
        settings_win.title("API设置")
        settings_win.geometry("520x430")
        settings_win.transient(self.root)
        settings_win.grab_set()
        
        # 百度翻译API设置
        baidu_frame = ttk.LabelFrame(settings_win, text="百度翻译API设置", padding="15")
        baidu_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(baidu_frame, text="申请地址: https://api.fanyi.baidu.com/",
                 foreground="blue", cursor="hand2").grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        ttk.Label(baidu_frame, text="APP ID:").grid(row=1, column=0, sticky=tk.W, pady=5)
        baidu_app_var = tk.StringVar(value=self.config.get('baidu_app_id', ''))
        baidu_app_entry = ttk.Entry(baidu_frame, textvariable=baidu_app_var, width=40)
        baidu_app_entry.grid(row=1, column=1, pady=5)
        
        ttk.Label(baidu_frame, text="密钥:").grid(row=2, column=0, sticky=tk.W, pady=5)
        baidu_key_var = tk.StringVar(value=self.config.get('baidu_secret_key', ''))
        baidu_key_entry = ttk.Entry(baidu_frame, textvariable=baidu_key_var, width=40)
        baidu_key_entry.grid(row=2, column=1, pady=5)
        
        # 绑定点击事件打开网址
        def open_baidu_site(event):
            webbrowser.open("https://api.fanyi.baidu.com/")
        
        settings_win.children['!labelframe'].winfo_children()[0].bind('<Button-1>', open_baidu_site)
        
        # 授权服务器设置
        license_frame = ttk.LabelFrame(settings_win, text="授权服务器设置", padding="15")
        license_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(license_frame, text="服务器地址:").grid(row=0, column=0, sticky=tk.W, pady=5)
        license_url_var = tk.StringVar(value=self.config.get('license_server_url', ''))
        license_url_entry = ttk.Entry(license_frame, textvariable=license_url_var, width=40)
        license_url_entry.grid(row=0, column=1, pady=5)

        ttk.Label(license_frame, text="API密钥:").grid(row=1, column=0, sticky=tk.W, pady=5)
        license_key_var = tk.StringVar(value=self.config.get('mc_api_secret', ''))
        license_key_entry = ttk.Entry(license_frame, textvariable=license_key_var, width=40, show="*")
        license_key_entry.grid(row=1, column=1, pady=5)

        # 保存按钮
        def save_settings():
            self.config['baidu_app_id'] = baidu_app_var.get()
            self.config['baidu_secret_key'] = baidu_key_var.get()
            self.config['license_server_url'] = license_url_var.get().strip()
            self.config['mc_api_secret'] = license_key_var.get().strip()
            
            # 重新初始化百度翻译器
            if baidu_app_var.get() and baidu_key_var.get():
                self.baidu_translator = BaiduTranslator(
                    baidu_app_var.get(),
                    baidu_key_var.get()
                )
                messagebox.showinfo("成功", "百度翻译API设置已保存")
                print("✅ 百度翻译API设置已保存")
            else:
                self.baidu_translator = None
                print("⚠️ 百度翻译API未配置")
            
            self.save_config()
            settings_win.destroy()
        
        btn_frame = ttk.Frame(settings_win)
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="保存设置", command=save_settings,
                  width=15).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="取消", command=settings_win.destroy,
                  width=15).pack(side=tk.LEFT, padx=10)
        
        # 聚焦到第一个输入框
        baidu_app_entry.focus_set()
    
    def test_translation_api(self):
        """测试翻译API"""
        print("🧪 开始测试翻译API...")
        
        test_text = "Hello World"
        print(f"🧪 测试文本: '{test_text}'")
        
        # 测试Google翻译
        result, error = self.google_translator.translate(test_text, 'auto', 'zh-CN')
        google_status = f"Google翻译: {'正常 ✓' if not error else '失败 ✗ - ' + error}"
        
        # 测试百度翻译
        if self.baidu_translator:
            result, error = self.baidu_translator.translate(test_text, 'auto', 'zh')
            baidu_status = f"百度翻译: {'正常 ✓' if not error else '失败 ✗ - ' + error}"
        else:
            baidu_status = "百度翻译: 未配置"
        
        messagebox.showinfo("API测试结果",
                          f"{google_status}\n{baidu_status}\n\n"
                          f"测试文本: '{test_text}'")
        print(f"🧪 API测试完成: {google_status}, {baidu_status}")
    
    def show_help(self):
        """显示帮助"""
        help_text = """
        Minecraft智能翻译工具 v2.3 使用说明
        
        ===== 核心功能 =====
        1. 智能翻译 - 自动检测语言并翻译
        2. 实时监控 - 过滤无用信息，只显示重要消息
        3. 语言检测 - 自动识别文本语言
        4. 消息过滤 - 过滤无用日志信息
        
        ===== 智能翻译特点 =====
        ✅ 自动检测输入文本的语言
        ✅ 只有当语言不同时才翻译
        ✅ 中文输入中文时不会重复翻译
        ✅ 支持中、英、日、韩等多种语言
        
        ===== 消息过滤 / 显示控制 =====
    ✅ 顶部控制栏同款开关也在菜单：设置 → 顶部控制栏 →（翻译选项 / 过滤与显示）
        ✅ 过滤声音警告、网络消息等无用信息
        ✅ 只保留玩家聊天和系统消息
        ✅ 自动提取玩家名和消息内容
        ✅ 可调整过滤敏感度
    ✅ 可开启“隐藏所有监控消息”：监控窗口不显示任何行（包括玩家聊天）
       - 仅影响监控显示；自动翻译仍可用（要停用请关闭“自动翻译”）
        
        ===== 使用步骤 =====
        1. 配置百度翻译API（已预配置）
        2. 启动Minecraft游戏
        3. 点击"启动监控"开始监控日志
        4. 在游戏中发送聊天消息测试
        
        ===== 快捷键 =====
        Ctrl + T : 智能翻译
        Ctrl + W : 网页翻译
        Ctrl + S : 保存翻译
        Ctrl + D : 语言检测测试
        
        ===== 问题解决 =====
        1. 监控不工作: 使用"手动选择日志文件"
        2. 翻译失败: 检查API配置和网络连接
        3. 过滤效果差: 使用"查看日志格式"调整
        
        注意: 本工具已预配置百度翻译API，可直接使用！
        """
        
        help_window = tk.Toplevel(self.root)
        help_window.title("使用说明")
        help_window.geometry("600x500")
        
        text_widget = scrolledtext.ScrolledText(help_window, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_widget.insert(tk.END, help_text)
        text_widget.config(state=tk.DISABLED)
        print("📖 显示帮助")
    def show_sponsor(self):
        """显示赞助信息"""
        sponsor_window = tk.Toplevel(self.root)
        sponsor_window.title("赞助")
        sponsor_window.geometry("320x140")
        ttk.Label(sponsor_window, text="【作者qq：3881015385】",
                  font=("Arial", 12, "bold")).pack(pady=25)
        ttk.Button(sponsor_window, text="确定", command=sponsor_window.destroy).pack(pady=5)
        print("💖 显示赞助信息")
    
    def show_about(self):
        """显示关于信息"""
        about_window = tk.Toplevel(self.root)
        about_window.title("关于")
        about_window.geometry("300x250")
        
        ttk.Label(about_window, text="Minecraft智能翻译工具",
                 font=("Arial", 14, "bold")).pack(pady=10)
        ttk.Label(about_window, text="版本: 2.1").pack(pady=5)
        ttk.Label(about_window, text="作者: YS").pack(pady=5)
        ttk.Label(about_window, text="功能: 智能语言检测和翻译").pack(pady=5)
        ttk.Label(about_window, text="新增: 过滤开关/隐藏监控消息").pack(pady=5)
        ttk.Label(about_window, text="支持: 百度翻译API").pack(pady=5)
        
        ttk.Button(about_window, text="确定", command=about_window.destroy).pack(pady=10)
        print("ℹ️ 显示关于信息")
    
    def _open_admin_panel(self):
        """默认实现：如果子类(MainApp)实现了管理员面板就调用；否则提示未实现。"""
        try:
            # 若当前对象已混入 main_window 的实现则直接调用
            if hasattr(super(), "_open_admin_panel"):
                return super()._open_admin_panel()  # type: ignore
        except Exception:
            pass
        try:
            from tkinter import messagebox
            messagebox.showinfo("提示", "管理员面板未初始化，请更新到支持管理员面板的版本。")
        except Exception:
            pass
    def run(self):
        # Ensure UI is initialized before using UI vars
        if not getattr(self, '_ui_ready', False):
            try:
                self._deferred_ui_init()
            except Exception:
                pass

        """运行程序"""
        print("\n" + "="*70)
        print("Minecraft智能翻译工具 v2.3 启动中...")
        print("="*70)
        
        # 居中显示
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
        # 绑定关闭事件
        def on_closing():
            print("\n" + "="*70)
            print("正在关闭程序...")
            
            if hasattr(self, 'log_monitor') and self.log_monitor.running:
                print("⏹️ 停止日志监控...")
                self.log_monitor.stop()
            
            # 保存配置
            print("💾 保存配置...")
            self.save_config()
            
            print("👋 程序已关闭")
            print("="*70)
            self.root.destroy()
        
        self.root.protocol("WM_DELETE_WINDOW", on_closing)
        
        # 显示启动提示
        self.status_var.set("就绪 | 已预配置百度翻译API，可直接使用！")
        
        print("✓ 程序启动完成")
        print("="*70)
        print("\n主要功能:")
        print("1. 智能语言检测和翻译")
        print("2. 自动过滤无用日志信息")
        print("3. 实时监控Minecraft聊天")
        print("4. 已预配置百度翻译API")
        print("="*70 + "\n")
        
        self.root.mainloop()
def main():
    """主函数"""
    print("="*70)
    print("Minecraft智能翻译工具 v2.0")
    print("="*70)
    print("功能特色:")
    print("1. 智能语言检测 - 自动识别文本语言")
    print("2. 消息过滤器 - 过滤无用日志信息")
    print("3. 百度翻译API - 已预配置，直接使用")
    print("4. 实时监控 - 只显示重要消息")
    print("5. 玩家信息提取 - 自动提取玩家名和消息")
    print("="*70)
    print("注意: 本版本已解决以下问题:")
    print("- 输入中文'我'不会再翻译成'我'")
    print("- 自动过滤声音警告等无用信息")
    print("- 只监控玩家聊天和系统消息")
    print("="*70)
    
    try:
        app = EnhancedMinecraftTranslator()
        app.run()
    except Exception as e:
        print(f"\n💥 程序启动失败: {e}")
        import traceback
        traceback.print_exc()
        input("按回车键退出...")
if __name__ == "__main__":
    main()
