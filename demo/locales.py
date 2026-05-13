# Copyright 2024 the LlamaFactory team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from demo.utils import csv_to_size_list
from demo.config import load_configuration
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
size_list_dict_CN = csv_to_size_list(os.path.join(base_dir, "assets/size_list_CN.csv"))
size_list_dict_EN = csv_to_size_list(os.path.join(base_dir, "assets/size_list_EN.csv"))
(
    size_list_config_CN,
    size_list_config_EN,
    color_list_dict_CN,
    color_list_dict_EN,
) = load_configuration(base_dir)


LOCALES = {
    "face_model": {
        "en": {
            "label": "Face detection model",
        },
        "zh": {
            "label": "人脸检测模型",
        },
        "ja": {
            "label": "顔検出モデル",
        },
        "ko": {
            "label": "얼굴 감지 모델",
        },
    },
    "matting_model": {
        "en": {
            "label": "Matting model",
        },
        "zh": {
            "label": "抠图模型",
        },
        "ja": {
            "label": "マッティングモデル",
        },
        "ko": {
            "label": "매팅 모델",
        },
    },
    "key_param": {
        "en": {
            "label": "Key Parameters",
        },
        "zh": {
            "label": "核心参数",
        },
        "ja": {
            "label": "主要パラメータ",
        },
        "ko": {
            "label": "주요 매개변수",
        },
    },
    "advance_param": {
        "en": {
            "label": "Advance Parameters",
        },
        "zh": {
            "label": "高级参数",
        },
        "ja": {
            "label": "詳細パラメータ",
        },
        "ko": {
            "label": "고급 매개변수",
        },
    },
    "size_mode": {
        "en": {
            "label": "ID photo size options",
            "choices": [
                "Size List",
                "Only Change BG",
                "Custom(px)",
                "Custom(mm)",
            ],
            "custom_size_eror": "The width should not be greater than the length; the length and width should not be less than 100, and no more than 1800.",
        },
        "zh": {
            "label": "证件照尺寸选项",
            "choices": ["尺寸列表", "只换底", "自定义(px)", "自定义(mm)"],
            "custom_size_eror": "宽度不应大于长度；长度和宽度不应小于100，不大于1800。",
        },
        "ja": {
            "label": "証明写真サイズオプション",
            "choices": [
                "サイズリスト",
                "背景のみ変更",
                "カスタムサイズ(px)",
                "カスタムサイズ(mm)",
            ],
            "custom_size_eror": "幅は長さより大きくしないでください。長さと幅は100以上1800以下にしてください。",
        },
        "ko": {
            "label": "증명사진 크기 옵션",
            "choices": [
                "크기 목록",
                "배경만 변경",
                "사용자 지정(px)",
                "사용자 지정(mm)",
            ],
            "custom_size_eror": "너비는 길이보다 크지 않아야 합니다; 길이와 너비는 100 이상 1800 이하여야 합니다.",
        },
    },
    "custom_size_px": {
        "en": {
            "height": "Height(px)",
            "width": "Width(px)",
        },
        "zh": {
            "height": "高度(px)",
            "width": "宽度(px)",
        },
        "ja": {
            "height": "高さ(px)",
            "width": "幅(px)",
        },
        "ko": {
            "height": "높이(px)",
            "width": "너비(px)",
        },
    },
    "custom_size_mm": {
        "en": {
            "height": "Height(mm)",
            "width": "Width(mm)",
        },
        "zh": {
            "height": "高度(mm)",
            "width": "宽度(mm)",
        },
        "ja": {
            "height": "高さ(mm)",
            "width": "幅(mm)",
        },
        "ko": {
            "height": "높이(mm)",
            "width": "너비(mm)",
        },
    },
    "size_list": {
        "en": {
            "label": "Size list",
            "choices": list(size_list_dict_EN.keys()),
            "develop": size_list_config_EN,
        },
        "zh": {
            "label": "预设尺寸",
            "choices": list(size_list_dict_CN.keys()),
            "develop": size_list_config_CN,
        },
        "ja": {
            "label": "サイズリスト",
            "choices": list(size_list_dict_EN.keys()),
            "develop": size_list_config_EN,
        },
        "ko": {
            "label": "크기 목록",
            "choices": list(size_list_dict_EN.keys()),
            "develop": size_list_config_EN,
        },
    },
    "bg_color": {
        "en": {
            "label": "Background color",
            "choices": list(color_list_dict_EN.keys()) + ["American Style"] + ["Custom(RGB)", "Custom(HEX)"],
            "develop": color_list_dict_EN,
        },
        "zh": {
            "label": "背景颜色",
            "choices": list(color_list_dict_CN.keys()) + ["美式证件照"] + ["自定义(RGB)", "自定义(HEX)"],
            "develop": color_list_dict_CN,
        },
        "ja": {
            "label": "背景色",
            "choices": list(color_list_dict_EN.keys()) + ["American Style"] + ["カスタム(RGB)", "カスタム(HEX)"],
            "develop": color_list_dict_EN,
        },
        "ko": {
            "label": "배경색",
            "choices": list(color_list_dict_EN.keys()) + ["American Style"] + ["사용자 지정(RGB)", "사용자 지정(HEX)"],
            "develop": color_list_dict_EN,
        },
    },
    "button": {
        "en": {
            "label": "Start",
        },
        "zh": {
            "label": "开始制作",
        },
        "ja": {
            "label": "開始",
        },
        "ko": {
            "label": "시작",
        },
    },
    "head_measure_ratio": {
        "en": {
            "label": "Head ratio",
        },
        "zh": {
            "label": "面部比例",
        },
        "ja": {
            "label": "頭部比率",
        },
        "ko": {
            "label": "머리 비율",
        },
    },
    "top_distance": {
        "en": {
            "label": "Top distance",
        },
        "zh": {
            "label": "头距顶距离",
        },
        "ja": {
            "label": "上部からの距離",
        },
        "ko": {
            "label": "상단 거리",
        },
    },
    "image_kb": {
        "en": {
            "label": "Set KB size",
            "choices": ["Not Set", "Custom"],
        },
        "zh": {
            "label": "设置 KB 大小",
            "choices": ["不设置", "自定义"],
        },
        "ja": {
            "label": "KBサイズを設定",
            "choices": ["設定なし", "カスタム"],
        },
        "ko": {
            "label": "KB 크기 설정",
            "choices": ["설정 안 함", "사용자 지정"],
        },
    },
    "image_kb_size": {
        "en": {
            "label": "KB size",
        },
        "zh": {
            "label": "KB 大小",
        },
        "ja": {
            "label": "KBサイズ",
        },
        "ko": {
            "label": "KB 크기",
        },
    },
    "image_dpi": {
        "en": {
            "label": "Set DPI",
            "choices": ["Not Set", "Custom"],
        },
        "zh": {
            "label": "设置 DPI 大小",
            "choices": ["不设置", "自定义"],
        },
        "ja": {
            "label": "DPIを設定",
            "choices": ["設定なし", "カスタム"],
        },
        "ko": {
            "label": "DPI 설정",
            "choices": ["설정 안 함", "사용자 지정"],
        },
    },
    "image_dpi_size": {
        "en": {
            "label": "DPI size",
        },
        "zh": {
            "label": "DPI 大小",
        },
        "ja": {
            "label": "DPIサイズ",
        },
        "ko": {
            "label": "DPI 크기",
        },
    },
    "render_mode": {
        "en": {
            "label": "Render mode",
            "choices": [
                "Solid Color",
                "Up-Down Gradient (White)",
                "Center Gradient (White)",
            ],
        },
        "zh": {
            "label": "渲染方式",
            "choices": ["纯色", "上下渐变（白色）", "中心渐变（白色）"],
        },
        "ja": {
            "label": "レンダリングモード",
            "choices": [
                "単色",
                "上下グラデーション（白）",
                "中心グラデーション（白）",
            ],
        },
        "ko": {
            "label": "렌더링 모드",
            "choices": [
                "단색",
                "위-아래 그라데이션 (흰색)",
                "중앙 그라데이션 (흰색)",
            ],
        },
    },
    # Tab3 - 水印工作台
    "watermark_tab": {
        "en": {
            "label": "Watermark",
        },
        "zh": {
            "label": "水印",
        },
        "ja": {
            "label": "ウォーターマーク",
        },
        "ko": {
            "label": "워터마크",
        },
    },
    "watermark_text": {
        "en": {
            "label": "Text",
            "value": "Hello",
            "placeholder": "up to 20 characters",
        },
        "zh": {
            "label": "水印文字",
            "value": "Hello",
            "placeholder": "最多20个字符",
        },
        "ja": {
            "label": "テキスト",
            "value": "Hello",
            "placeholder": "最大20文字",
        },
        "ko": {
            "label": "텍스트",
            "value": "Hello",
            "placeholder": "최대 20자",
        },
    },
    "watermark_color": {
        "en": {
            "label": "Color",
        },
        "zh": {
            "label": "水印颜色",
        },
        "ja": {
            "label": "色",
        },
        "ko": {
            "label": "색상",
        },
    },
    "watermark_size": {
        "en": {
            "label": "Size",
        },
        "zh": {
            "label": "文字大小",
        },
        "ja": {
            "label": "サイズ",
        },
        "ko": {
            "label": "크기",
        },
    },
    "watermark_opacity": {
        "en": {
            "label": "Opacity",
        },
        "zh": {
            "label": "水印透明度",
        },
        "ja": {
            "label": "不透明度",
        },
        "ko": {
            "label": "불투명도",
        },
    },
    "watermark_angle": {
        "en": {
            "label": "Angle",
        },
        "zh": {
            "label": "水印角度",
        },
        "ja": {
            "label": "角度",
        },
        "ko": {
            "label": "각도",
        },
    },
    "watermark_space": {
        "en": {
            "label": "Space",
        },
        "zh": {
            "label": "水印间距",
        },
        "ja": {
            "label": "間隔",
        },
        "ko": {
            "label": "간격",
        },
    },
    "watermark_switch": {
        "en": {
            "label": "Watermark",
            "value": "Not Add",
            "choices": ["Not Add", "Add"],
        },
        "zh": {
            "label": "水印",
            "value": "不添加",
            "choices": ["不添加", "添加"],
        },
        "ja": {
            "label": "ウォーターマーク",
            "value": "追加しない",
            "choices": ["追加しない", "追加"],
        },
        "ko": {
            "label": "워터마크",
            "value": "추가하지 않음",
            "choices": ["추가하지 않음", "추가"],
        },
    },
    # 输出结果
    "notification": {
        "en": {
            "label": "notification",
            "face_error": "The number of faces is not equal to 1, please upload an image with a single face. If the actual number of faces is 1, it may be an issue with the accuracy of the detection model. Please switch to a different face detection model on the left or raise a Github Issue to notify the author.",
        },
        "zh": {
            "label": "通知",
            "face_error": "人脸数不等于1，请上传单人照片。如果实际人脸数为1，可能是检测模型的准确度问题，请切换左侧不同的人脸检测模型或提出Github Issue通知作者。",
        },
        "ja": {
            "label": "通知",
            "face_error": "顔の数が1ではありません。1つの顔を含む画像をアップロードしてください。実際の顔の数が1の場合、検出モデルの精度の問題かもしれません。左側で別の顔検出モデルに切り替えるか、Githubの問題を作成して作者に通知してください。",
        },
        "ko": {
            "label": "알림",
            "face_error": "얼굴 수가 1이 아닙니다. 단일 얼굴이 있는 이미지를 업로드해 주세요. 실제 얼굴 수가 1인 경우 감지 모델의 정확도 문제일 수 있습니다. 왼쪽에서 다른 얼굴 감지 모델로 전환하거나 Github Issue를 제기하여 작성자에게 알려주세요.",
        },
    },
    "standard_photo": {
        "en": {
            "label": "Standard photo",
        },
        "zh": {
            "label": "标准照",
        },
        "ja": {
            "label": "標準写真",
        },
        "ko": {
            "label": "표준 사진",
        },
    },
    "hd_photo": {
        "en": {
            "label": "HD photo",
        },
        "zh": {
            "label": "高清照",
        },
        "ja": {
            "label": "HD写真",
        },
        "ko": {
            "label": "HD 사진",
        },
    },
    "standard_photo_png": {
        "en": {
            "label": "Matting Standard photo",
        },
        "zh": {
            "label": "透明标准照",
        },
        "ja": {
            "label": "マッティング標準写真",
        },
        "ko": {
            "label": "매팅 표준 사진",
        },
    },
    "hd_photo_png": {
        "en": {
            "label": "Matting HD photo",
        },
        "zh": {
            "label": "透明高清照",
        },
        "ja": {
            "label": "マッティングHD写真",
        },
        "ko": {
            "label": "매팅 HD 사진",
        },
    },
    "layout_photo": {
        "en": {
            "label": "Layout photo",
        },
        "zh": {
            "label": "排版照",
        },
        "ja": {
            "label": "レイアウト写真",
        },
        "ko": {
            "label": "레이아웃 사진",
        },
    },
    "download": {
        "en": {
            "label": "Download the photo after adjusting the DPI or KB size",
        },
        "zh": {
            "label": "下载调整 DPI 或 KB 大小后的照片",
        },
        "ja": {
            "label": "DPIまたはKBサイズ調整後の写真をダウンロード",
        },
        "ko": {
            "label": "DPI 또는 KB 크기 조정 후 사진 다운로드",
        },
    },
    "matting_image": {
        "en": {
            "label": "Matting image",
        },
        "zh": {
            "label": "抠图图像",
        },
        "ja": {
            "label": "マット画像",
        },
        "ko": {
            "label": "매팅 이미지",
        },
    },
    "beauty_tab": {
        "en": {
            "label": "Beauty",
        },
        "zh": {
            "label": "美颜",
        },
        "ja": {
            "label": "美顔",
        },
        "ko": {
            "label": "뷰티",
        },
    },
    "whitening_strength": {
        "en": {
            "label": "whitening strength",
        },
        "zh": {
            "label": "美白强度",
        },
        "ja": {
            "label": "美白強度",
        },
        "ko": {
            "label": "미백 강도",
        },
    },
    "brightness_strength": {
        "en": {
            "label": "brightness strength",
        },
        "zh": {
            "label": "亮度强度",
        },
        "ja": {
            "label": "明るさの強さ",
        },
        "ko": {
            "label": "밝기 강도",
        },
    },
    "contrast_strength": {
        "en": {
            "label": "contrast strength",
        },
        "zh": {
            "label": "对比度强度",
        },
        "ja": {
            "label": "コントラスト強度",
        },
        "ko": {
            "label": "대비 강도",
        },
    },
    "sharpen_strength": {
        "en": {
            "label": "sharpen strength",
        },
        "zh": {
            "label": "锐化强度",
        },
        "ja": {
            "label": "シャープ化強度",
        },
        "ko": {
            "label": "샤ープ 강도",
        },
    },
    "saturation_strength": {
        "en": {
            "label": "saturation strength",
        },
        "zh": {
            "label": "饱和度强度",
        },
        "ja": {
            "label": "飽和度強度",
        },
        "ko": {
            "label": "포화도 강도",
        },
    },
    "plugin": {
        "en": {
            "label": "🤖Plugin",
            "choices": ["Face Alignment", "Horizontal Flip", "Layout Photo Crop Line", "JPEG Format", "Five Inch Paper"],
            "value": ["Layout Photo Crop Line"]
        },
        "zh": {
            "label": "🤖插件",
            "choices": ["人脸旋转对齐", "水平翻转", "排版照裁剪线", "JPEG格式"],
            "value": ["排版照裁剪线"]
        },
        "ja": {
            "label": "🤖プラグイン",
            "choices": ["顔の整列", "水平反転", "レイアウト写真の切り取り線", "JPEGフォーマット"],
            "value": ["レイアウト写真の切り取り線"]
        },
        "ko": {
            "label": "🤖플러그인",
            "choices": ["얼굴 정렬", "수평 반전", "레이아웃 사진 자르기 선", "JPEG 포맷", "오렌지 사진"],
            "value": ["레이아웃 사진 자르기 선"]
        },
    },
    "template_photo": {
        "en": {
            "label": "Social Media Template Photo",
        },
        "zh": {
            "label": "社交媒体模版照",
        },
        "ja": {
            "label": "SNS テンプレート写真",
        },
        "ko": {
            "label": "SNS 템플릿 사진",
        },
    },
    "ai_enhance": {
        "en": {
            "section_label": "AI Enhance Preview",
            "enable_label": "Enable AI enhancement preview",
            "consent_label": "I understand this image will be uploaded to a third-party AI service",
            "mode_label": "AI mode",
            "mode_choices": ["repair", "background_template", "outfit"],
            "preview_label": "AI preview comparison",
            "input_preview_label": "AI input preview (sent to provider)",
            "output_preview_label": "AI output preview",
            "template_label": "Template",
            "background_template_label": "Background template",
            "outfit_template_label": "Outfit template (Beta)",
            "template_choices": ["clean_blue", "clean_white", "clean_gray", "resume_soft", "linkedin_clean"],
            "outfit_template_choices": ["business_suit_black", "business_suit_navy", "white_shirt", "business_casual"],
            "status_label": "AI status",
            "initial_status": "AI status will be shown after generation. Outfit is an AI formalwear preview for resume/profile reference only, not recommended for official ID submissions.",
            "disabled_status": "AI enhancement not enabled",
            "consent_required_status": "AI enhancement skipped: consent required before upload",
            "success_status": "AI enhancement preview generated",
            "validation_pass_label": "validation=pass",
            "validation_fail_label": "validation=fail",
            "fallback_status": "AI enhancement fallback used",
            "fallback_output_not_shown_status": "AI output did not pass the quality gate and has been rolled back; it is not shown as a successful output",
            "color_cast_status": "AI output shows obvious color cast and has been rolled back",
            "failed_status": "AI enhancement failed",
            "face_error": "AI preview not generated because the base photo generation failed",
            "wait_hint": "AI generation may take 1–2 minutes, please do not click repeatedly",
            "outfit_notice_status": "Outfit is an AI formalwear preview for resume/profile reference only, not recommended for official ID submissions",
            "rate_limited_status": "Request limit reached, please try again later",
            "concurrency_limited_status": "Another AI request is still running, please wait",
        },
        "zh": {
            "section_label": "AI 增强预览",
            "enable_label": "启用 AI 增强预览",
            "consent_label": "我已知晓该图片会上传到第三方 AI 服务",
            "mode_label": "AI 模式",
            "mode_choices": ["repair", "background_template", "outfit"],
            "preview_label": "AI 前后对比预览",
            "input_preview_label": "AI 输入预览（发送给 provider）",
            "output_preview_label": "AI 输出预览",
            "template_label": "模板",
            "background_template_label": "背景模板",
            "outfit_template_label": "正装模板（Beta）",
            "template_choices": ["clean_blue", "clean_white", "clean_gray", "resume_soft", "linkedin_clean"],
            "outfit_template_choices": ["business_suit_black", "business_suit_navy", "white_shirt", "business_casual"],
            "status_label": "AI 状态",
            "initial_status": "AI 状态将在生成后显示。outfit 是 AI 正装预览，仅用于简历头像/形象照参考，不建议作为正式证件照提交。",
            "disabled_status": "未启用 AI 增强",
            "consent_required_status": "AI 增强已跳过：需先同意上传到第三方 AI 服务",
            "success_status": "AI 增强预览已生成",
            "validation_pass_label": "validation=pass",
            "validation_fail_label": "validation=fail",
            "fallback_status": "AI 增强使用了降级结果",
            "fallback_output_not_shown_status": "AI 输出未通过质量门禁，已回退，不展示为成功输出",
            "color_cast_status": "AI 输出检测到明显色偏，已回退",
            "failed_status": "AI 增强失败",
            "face_error": "基础证件照生成失败，未生成 AI 预览",
            "wait_hint": "AI 生成可能需要 1–2 分钟，请勿重复点击",
            "outfit_notice_status": "outfit 是 AI 正装预览，仅用于简历头像/形象照参考，不建议作为正式证件照提交",
            "rate_limited_status": "请求次数已达上限，请稍后再试",
            "concurrency_limited_status": "已有 AI 请求在处理中，请等待当前请求完成",
        },
        "ja": {
            "section_label": "AI 強化プレビュー",
            "enable_label": "AI 強化プレビューを有効化",
            "consent_label": "この画像がサードパーティの AI サービスにアップロードされることを理解しました",
            "mode_label": "AI モード",
            "mode_choices": ["repair", "background_template", "outfit"],
            "preview_label": "AI 前後比較プレビュー",
            "input_preview_label": "AI 入力プレビュー（provider に送信）",
            "output_preview_label": "AI 出力プレビュー",
            "template_label": "テンプレート",
            "background_template_label": "背景テンプレート",
            "outfit_template_label": "服装テンプレート（Beta）",
            "template_choices": ["clean_blue", "clean_white", "clean_gray", "resume_soft", "linkedin_clean"],
            "outfit_template_choices": ["business_suit_black", "business_suit_navy", "white_shirt", "business_casual"],
            "status_label": "AI ステータス",
            "initial_status": "AI ステータスは生成後に表示されます。outfit は履歴書/プロフィール向けの AI 正装プレビューで、正式な証明写真提出には推奨されません。",
            "disabled_status": "AI 強化は有効化されていません",
            "consent_required_status": "AI 強化をスキップしました：アップロード同意が必要です",
            "success_status": "AI 強化プレビューを生成しました",
            "validation_pass_label": "validation=pass",
            "validation_fail_label": "validation=fail",
            "fallback_status": "AI 強化はフォールバック結果を使用しました",
            "fallback_output_not_shown_status": "AI 出力は品質ゲートを通過しなかったためロールバックされ、成功出力として表示しません",
            "color_cast_status": "AI 出力に明らかな色かぶりを検出したためロールバックしました",
            "failed_status": "AI 強化に失敗しました",
            "face_error": "元の証明写真生成が失敗したため、AI プレビューは生成されませんでした",
            "wait_hint": "AI 生成には1〜2分かかる場合があります。繰り返しクリックしないでください",
            "outfit_notice_status": "outfit は履歴書/プロフィール向けの AI 正装プレビューで、正式な証明写真提出には推奨されません",
            "rate_limited_status": "リクエスト上限に達しました。しばらく待ってから再試行してください",
            "concurrency_limited_status": "別の AI リクエストを処理中です。完了までお待ちください",
        },
        "ko": {
            "section_label": "AI 향상 미리보기",
            "enable_label": "AI 향상 미리보기 사용",
            "consent_label": "이 이미지가 제3자 AI 서비스에 업로드된다는 점을 이해했습니다",
            "mode_label": "AI 모드",
            "mode_choices": ["repair", "background_template", "outfit"],
            "preview_label": "AI 전후 비교 미리보기",
            "input_preview_label": "AI 입력 미리보기(provider 전송)",
            "output_preview_label": "AI 출력 미리보기",
            "template_label": "템플릿",
            "background_template_label": "배경 템플릿",
            "outfit_template_label": "의상 템플릿(Beta)",
            "template_choices": ["clean_blue", "clean_white", "clean_gray", "resume_soft", "linkedin_clean"],
            "outfit_template_choices": ["business_suit_black", "business_suit_navy", "white_shirt", "business_casual"],
            "status_label": "AI 상태",
            "initial_status": "AI 상태는 생성 후 표시됩니다. outfit은 이력서/프로필 참고용 AI 정장 미리보기이며 공식 신분증 사진 제출에는 권장하지 않습니다.",
            "disabled_status": "AI 향상이 활성화되지 않았습니다",
            "consent_required_status": "AI 향상을 건너뛰었습니다: 업로드 동의가 필요합니다",
            "success_status": "AI 향상 미리보기가 생성되었습니다",
            "validation_pass_label": "validation=pass",
            "validation_fail_label": "validation=fail",
            "fallback_status": "AI 향상에서 폴백 결과를 사용했습니다",
            "fallback_output_not_shown_status": "AI 출력이 품질 게이트를 통과하지 못해 롤백되었으며 성공 출력으로 표시하지 않습니다",
            "color_cast_status": "AI 출력에서 뚜렷한 색상 왜곡이 감지되어 롤백되었습니다",
            "failed_status": "AI 향상 실패",
            "face_error": "기본 증명사진 생성에 실패하여 AI 미리보기를 만들지 못했습니다",
            "wait_hint": "AI 생성에는 1–2분이 걸릴 수 있으니 반복 클릭하지 마세요",
            "outfit_notice_status": "outfit은 이력서/프로필 참고용 AI 정장 미리보기이며 공식 신분증 사진 제출에는 권장하지 않습니다",
            "rate_limited_status": "요청 한도에 도달했습니다. 잠시 후 다시 시도하세요",
            "concurrency_limited_status": "다른 AI 요청이 아직 처리 중입니다. 잠시 기다려 주세요",
        },
    },
    "print_tab": {
        "en": {
            "label": "Print Layout",
        },
        "zh": {
            "label": "打印排版",
        },
        "ja": {
            "label": "印刷レイアウト",
        },
        "ko": {
            "label": "인쇄 레이아웃",
        },
    },
    "print_switch": {
        "shape": [[1205, 1795], [1051, 1500], [2479, 3508], [1051, 1500], [1205, 1795]],
        "en": {
            "label": "Paper size",
            "choices": ["6 inch", "5 inch", "A4", "3R", "4R"],
        },
        "zh": {
            "label": "相纸选择",
            "choices": ["六寸", "五寸", "A4", "3R", "4R"],
        },
        "ja": {
            "label": "用紙サイズ",
            "choices": ["6インチ", "5インチ", "A4", "3R", "4R"],
        },
        "ko": {
            "label": "용지 사이즈",
            "choices": ["6인치", "5인치", "A4", "3R", "4R"],
        },
    },
}
