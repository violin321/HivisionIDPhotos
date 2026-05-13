import numpy as np
import cv2
from hivision import IDCreator
from hivision.error import FaceError, APIError
from hivision.utils import (
    add_background,
    add_background_with_image,
    resize_image_to_kb,
    add_watermark,
    save_image_dpi_to_bytes,
    bytes_2_base64,
    base64_2_numpy,
)
from hivision.creator.layout_calculator import (
    generate_layout_array,
    generate_layout_image,
)
from hivision.creator.choose_handler import choose_handler
from hivision.plugin.template.template_calculator import generte_template_photo
from demo.utils import range_check
import gradio as gr
import os
import cv2
import time
from demo.locales import LOCALES
from hivision.plugin.ai_enhance import AIEnhanceRequest, AIEnhanceService
from hivision.plugin.ai_enhance.errors import AIEnhanceValidationError


AI_BACKGROUND_TEMPLATE_DEFAULT = "clean_blue"
AI_OUTFIT_TEMPLATE_DEFAULT = "business_suit_black"


base_path = os.path.dirname(os.path.abspath(__file__))

class IDPhotoProcessor:
    def __init__(self):
        self.ai_enhance_service = AIEnhanceService()

    def process(
        self,
        input_image,
        mode_option,
        size_list_option,
        color_option,
        render_option,
        image_kb_options,
        custom_color_R,
        custom_color_G,
        custom_color_B,
        custom_color_hex_value,
        custom_size_height,
        custom_size_width,
        custom_size_height_mm,
        custom_size_width_mm,
        custom_image_kb,
        language,
        matting_model_option,
        watermark_option,
        watermark_text,
        watermark_text_color,
        watermark_text_size,
        watermark_text_opacity,
        watermark_text_angle,
        watermark_text_space,
        face_detect_option,
        head_measure_ratio=0.2,
        top_distance_max=0.12,
        whitening_strength=0,
        image_dpi_option=False,
        custom_image_dpi=None,
        brightness_strength=0,
        contrast_strength=0,
        sharpen_strength=0,
        saturation_strength=0,
        plugin_option=[],
        print_switch=None,
        enable_ai_enhance=False,
        ai_consent=False,
        ai_mode="repair",
        ai_template_name=AI_BACKGROUND_TEMPLATE_DEFAULT,
    ):
        # 初始化参数
        top_distance_min = top_distance_max - 0.02
        # 得到render_option在LOCALES["render_mode"][language]["choices"]中的索引
        render_option_index = LOCALES["render_mode"][language]["choices"].index(
            render_option
        )
        # 读取插件选项
        # 人脸对齐选项
        if LOCALES["plugin"][language]["choices"][0] in plugin_option:
            face_alignment_option = True
        else:
            face_alignment_option = False
        # 水平翻转选项
        if LOCALES["plugin"][language]["choices"][1] in plugin_option:
            horizontal_flip_option = True
        else:
            horizontal_flip_option = False
        # 排版裁剪线选项
        if LOCALES["plugin"][language]["choices"][2] in plugin_option:
            layout_photo_crop_line_option = True
        else:
            layout_photo_crop_line_option = False
        # JPEG格式选项
        if LOCALES["plugin"][language]["choices"][3] in plugin_option:
            jpeg_format_option = True
        else:
            jpeg_format_option = False
        
        idphoto_json = self._initialize_idphoto_json(
            mode_option, color_option, render_option_index, image_kb_options, layout_photo_crop_line_option, jpeg_format_option, print_switch
        )

        # 处理尺寸模式
        size_result = self._process_size_mode(
            idphoto_json,
            language,
            size_list_option,
            custom_size_height,
            custom_size_width,
            custom_size_height_mm,
            custom_size_width_mm,
        )
        if isinstance(size_result, list):
            return size_result  # 返回错误信息

        # 处理颜色模式
        self._process_color_mode(
            idphoto_json,
            language,
            color_option,
            custom_color_R,
            custom_color_G,
            custom_color_B,
            custom_color_hex_value,
        )

        # 如果设置了自定义KB大小
        if (
            idphoto_json["image_kb_mode"]
            == LOCALES["image_kb"][language]["choices"][-1]
        ):
            idphoto_json["custom_image_kb"] = custom_image_kb

        # 如果设置了自定义DPI大小
        if image_dpi_option == LOCALES["image_dpi"][language]["choices"][-1]:
            idphoto_json["custom_image_dpi"] = custom_image_dpi

        # 创建IDCreator实例并设置处理器
        creator = IDCreator()
        choose_handler(creator, matting_model_option, face_detect_option)

        # 生成证件照
        try:
            result = self._generate_id_photo(
                creator,
                input_image,
                idphoto_json,
                language,
                head_measure_ratio,
                top_distance_max,
                top_distance_min,
                whitening_strength,
                brightness_strength,
                contrast_strength,
                sharpen_strength,
                saturation_strength,
                face_alignment_option,
                horizontal_flip_option,
            )
        except (FaceError, APIError):
            return self._handle_photo_generation_error(language)

        # 后处理生成的照片
        return self._process_generated_photo(
            result,
            idphoto_json,
            language,
            watermark_option,
            watermark_text,
            watermark_text_size,
            watermark_text_opacity,
            watermark_text_angle,
            watermark_text_space,
            watermark_text_color,
            enable_ai_enhance=enable_ai_enhance,
            ai_consent=ai_consent,
            ai_mode=ai_mode,
            ai_template_name=ai_template_name,
        )

    # 初始化idphoto_json字典
    def _initialize_idphoto_json(
        self,
        mode_option,
        color_option,
        render_option,
        image_kb_options,
        layout_photo_crop_line_option,
        jpeg_format_option,
        print_switch,
    ):
        """初始化idphoto_json字典"""
        return {
            "size_mode": mode_option,
            "color_mode": color_option,
            "render_mode": render_option,
            "image_kb_mode": image_kb_options,
            "custom_image_kb": None,
            "custom_image_dpi": None,
            "layout_photo_crop_line_option": layout_photo_crop_line_option,
            "jpeg_format_option": jpeg_format_option,
            "print_switch": print_switch,
        }

    # 处理尺寸模式
    def _process_size_mode(
        self,
        idphoto_json,
        language,
        size_list_option,
        custom_size_height,
        custom_size_width,
        custom_size_height_mm,
        custom_size_width_mm,
    ):
        """处理尺寸模式"""
        # 如果选择了尺寸列表
        if idphoto_json["size_mode"] == LOCALES["size_mode"][language]["choices"][0]:
            idphoto_json["size"] = LOCALES["size_list"][language]["develop"][
                size_list_option
            ]
        # 如果选择了自定义尺寸(px或mm)
        elif (
            idphoto_json["size_mode"] == LOCALES["size_mode"][language]["choices"][2]
            or idphoto_json["size_mode"] == LOCALES["size_mode"][language]["choices"][3]
        ):
            # 如果选择了自定义尺寸(px)
            if (
                idphoto_json["size_mode"]
                == LOCALES["size_mode"][language]["choices"][2]
            ):
                id_height, id_width = int(custom_size_height), int(custom_size_width)
            # 如果选择了自定义尺寸(mm)
            else:
                # 将mm转换为px
                id_height = int(custom_size_height_mm / 25.4 * 300)
                id_width = int(custom_size_width_mm / 25.4 * 300)
            # 检查尺寸像素是否在100到1800之间
            if (
                id_height < id_width
                or min(id_height, id_width) < 100
                or max(id_height, id_width) > 1800
            ):
                return self._create_error_response(language)
            idphoto_json["size"] = (id_height, id_width)
        # 如果选择了只换底
        else:
            idphoto_json["size"] = (None, None)

    # 处理颜色模式
    def _process_color_mode(
        self,
        idphoto_json,
        language,
        color_option,
        custom_color_R,
        custom_color_G,
        custom_color_B,
        custom_color_hex_value,
    ):
        """处理颜色模式"""
        # 如果选择了自定义颜色BGR
        if idphoto_json["color_mode"] == LOCALES["bg_color"][language]["choices"][-2]:
            idphoto_json["color_bgr"] = tuple(
                map(range_check, [custom_color_R, custom_color_G, custom_color_B])
            )
        # 如果选择了自定义颜色HEX
        elif idphoto_json["color_mode"] == LOCALES["bg_color"][language]["choices"][-1]:
            hex_color = custom_color_hex_value
            # 将十六进制颜色转换为RGB颜色，如果长度为6，则直接转换，如果长度为7，则去掉#号再转换
            if len(hex_color) == 6:
                idphoto_json["color_bgr"] = tuple(
                    int(hex_color[i : i + 2], 16) for i in (0, 2, 4)
                )
            elif len(hex_color) == 7:
                hex_color = hex_color[1:]
                idphoto_json["color_bgr"] = tuple(
                    int(hex_color[i : i + 2], 16) for i in (0, 2, 4)
                )
            else:
                raise ValueError(
                    "Invalid hex color. You can only use 6 or 7 characters. For example: #FFFFFF or FFFFFF"
                )
        # 如果选择了美式证件照
        elif idphoto_json["color_mode"] == LOCALES["bg_color"][language]["choices"][-3]:
            idphoto_json["color_bgr"] = (255, 255, 255)
        else:
            hex_color = LOCALES["bg_color"][language]["develop"][color_option]
            idphoto_json["color_bgr"] = tuple(
                int(hex_color[i : i + 2], 16) for i in (0, 2, 4)
            )

    # 生成证件照
    def _generate_id_photo(
        self,
        creator: IDCreator,
        input_image,
        idphoto_json,
        language,
        head_measure_ratio,
        top_distance_max,
        top_distance_min,
        whitening_strength,
        brightness_strength,
        contrast_strength,
        sharpen_strength,
        saturation_strength,
        face_alignment_option,
        horizontal_flip_option,
    ):
        """生成证件照"""
        change_bg_only = (
            idphoto_json["size_mode"] in LOCALES["size_mode"][language]["choices"][1]
        )
        return creator(
            input_image,
            change_bg_only=change_bg_only,
            size=idphoto_json["size"],
            head_measure_ratio=head_measure_ratio,
            head_top_range=(top_distance_max, top_distance_min),
            whitening_strength=whitening_strength,
            brightness_strength=brightness_strength,
            contrast_strength=contrast_strength,
            sharpen_strength=sharpen_strength,
            saturation_strength=saturation_strength,
            face_alignment=face_alignment_option,
            horizontal_flip=horizontal_flip_option,
        )

    # 处理照片生成错误
    def _handle_photo_generation_error(self, language):
        """处理照片生成错误"""
        return [gr.update(value=None) for _ in range(4)] + [
            gr.update(visible=False, value=None),
            gr.update(value=None, visible=False),
            gr.update(visible=False),
            gr.update(
                value=LOCALES["notification"][language]["face_error"], visible=True
            ),
            gr.update(value=None),
            gr.update(value=None),
            gr.update(value=LOCALES["ai_enhance"][language]["face_error"], visible=True),
        ]

    # 处理生成的照片
    def _process_generated_photo(
        self,
        result,
        idphoto_json,
        language,
        watermark_option,
        watermark_text,
        watermark_text_size,
        watermark_text_opacity,
        watermark_text_angle,
        watermark_text_space,
        watermark_text_color,
        enable_ai_enhance=False,
        ai_consent=False,
        ai_mode="repair",
        ai_template_name=AI_BACKGROUND_TEMPLATE_DEFAULT,
    ):
        """处理生成的照片"""
        result_image_standard, result_image_hd, _, _, _, _ = result
        result_image_standard_png = np.uint8(result_image_standard)
        result_image_hd_png = np.uint8(result_image_hd)

        # 渲染背景
        result_image_standard, result_image_hd = self._render_background(
            result_image_standard, result_image_hd, idphoto_json, language
        )

        # 添加水印
        if watermark_option == LOCALES["watermark_switch"][language]["choices"][1]:
            result_image_standard, result_image_hd = self._add_watermark(
                result_image_standard,
                result_image_hd,
                watermark_text,
                watermark_text_size,
                watermark_text_opacity,
                watermark_text_angle,
                watermark_text_space,
                watermark_text_color,
            )
        
        # 生成排版照片
        result_image_layout, result_image_layout_visible = self._generate_image_layout(
            idphoto_json,
            result_image_standard,
            language,
        )
        
        # 生成模板照片
        result_image_template, result_image_template_visible = self._generate_image_template(
            idphoto_json,
            result_image_hd,
            language,
        )

        # 调整图片大小
        output_image_path_dict = self._save_image(
            result_image_standard,
            result_image_hd,
            result_image_layout,
            idphoto_json,
            format="jpeg" if idphoto_json["jpeg_format_option"] else "png",
        )

        ai_input_preview_image, ai_output_preview_image, ai_status_text = self._run_ai_enhance_preview(
            result_image_hd=result_image_hd,
            language=language,
            enable_ai_enhance=enable_ai_enhance,
            ai_consent=ai_consent,
            ai_mode=ai_mode,
            ai_template_name=ai_template_name,
        )
        
        # 返回
        if result_image_layout is not None:
            result_image_layout = output_image_path_dict["layout"]["path"]
            
        return self._create_response(
            output_image_path_dict["standard"]["path"],
            output_image_path_dict["hd"]["path"],
            result_image_standard_png,
            result_image_hd_png,
            gr.update(value=result_image_layout, visible=result_image_layout_visible),
            gr.update(value=result_image_template, visible=result_image_template_visible),
            gr.update(visible = result_image_template_visible),
            ai_input_preview_image,
            ai_output_preview_image,
            ai_status_text,
        )

    # 渲染背景
    def _render_background(self, result_image_standard, result_image_hd, idphoto_json, language):
        """渲染背景"""
        render_modes = {0: "pure_color", 1: "updown_gradient", 2: "center_gradient"}
        render_mode = render_modes[idphoto_json["render_mode"]]

        if idphoto_json["color_mode"] != LOCALES["bg_color"][language]["choices"][-3]:
            result_image_standard = np.uint8(
                add_background(
                    result_image_standard, bgr=idphoto_json["color_bgr"], mode=render_mode
                )
            )
            result_image_hd = np.uint8(
                add_background(
                    result_image_hd, bgr=idphoto_json["color_bgr"], mode=render_mode
                )
            )
        # 如果选择了美式证件照
        else:
            result_image_standard = np.uint8(
                add_background_with_image(
                    result_image_standard, 
                    background_image=cv2.imread(os.path.join(base_path, "assets", "american-style.png"))
                )
            )
            result_image_hd = np.uint8(
                add_background_with_image(
                    result_image_hd, 
                    background_image=cv2.imread(os.path.join(base_path, "assets", "american-style.png"))
                )
            )
        return result_image_standard, result_image_hd

    # 生成排版照片
    def _generate_image_layout(
        self,
        idphoto_json,
        result_image_standard,
        language,
    ):
        """生成排版照片"""
        # 如果选择了只换底，则不生成排版照片
        if idphoto_json["size_mode"] in LOCALES["size_mode"][language]["choices"][1]:
            return None, False

        # 预设排版照尺寸字典
        PRESET_LAYOUT_SIZE = {
            choice: shape
            for choice, shape in zip(
                LOCALES["print_switch"][language]["choices"],
                LOCALES["print_switch"]["shape"]
            )
        }
        
        choose_layout_size = PRESET_LAYOUT_SIZE[idphoto_json["print_switch"]]
        
        typography_arr, typography_rotate = generate_layout_array(
            input_height=idphoto_json["size"][0],
            input_width=idphoto_json["size"][1],
            LAYOUT_HEIGHT= choose_layout_size[0],
            LAYOUT_WIDTH= choose_layout_size[1],
        )
        
        result_image_layout = generate_layout_image(
            result_image_standard,
            typography_arr,
            typography_rotate,
            height=idphoto_json["size"][0],
            width=idphoto_json["size"][1],
            crop_line=idphoto_json["layout_photo_crop_line_option"],
            LAYOUT_HEIGHT=choose_layout_size[0],
            LAYOUT_WIDTH=choose_layout_size[1],
        )

        return result_image_layout, True
    
    # 生成模板照片
    def _generate_image_template(
        self,
        idphoto_json,
        result_image_hd,
        language,
    ):
        # 如果选择了只换底，则不生成模板照片
        if idphoto_json["size_mode"] in LOCALES["size_mode"][language]["choices"][1]:
            return None, False
        
        TEMPLATE_NAME_LIST = ["template_1", "template_2"]
        """生成模板照片"""
        result_image_template_list = []
        for template_name in TEMPLATE_NAME_LIST:
            result_image_template = generte_template_photo(
                template_name=template_name,
                input_image=result_image_hd,
            )
            result_image_template_list.append(result_image_template)
        return result_image_template_list, True

    # 添加水印
    def _add_watermark(
        self,
        result_image_standard,
        result_image_hd,
        watermark_text,
        watermark_text_size,
        watermark_text_opacity,
        watermark_text_angle,
        watermark_text_space,
        watermark_text_color,
    ):
        """添加水印"""
        watermark_params = {
            "text": watermark_text,
            "size": watermark_text_size,
            "opacity": watermark_text_opacity,
            "angle": watermark_text_angle,
            "space": watermark_text_space,
            "color": watermark_text_color,
        }
        result_image_standard = add_watermark(
            image=result_image_standard, **watermark_params
        )
        result_image_hd = add_watermark(image=result_image_hd, **watermark_params)
        return result_image_standard, result_image_hd

    def _save_image(
        self,
        result_image_standard,
        result_image_hd,
        result_image_layout,
        idphoto_json,
        format="png",
    ):
        # 设置输出路径（临时目录）
        import tempfile
        base_path = tempfile.mkdtemp()
        timestamp = int(time.time())
        output_paths = {
            "standard": {
                "path": f"{base_path}/{timestamp}_standard",
                "processed": False,
            },
            "hd": {"path": f"{base_path}/{timestamp}_hd", "processed": False},
            "layout": {"path": f"{base_path}/{timestamp}_layout", "processed": False},
        }

        # 获取自定义的KB和DPI值
        custom_kb = idphoto_json.get("custom_image_kb")
        custom_dpi = idphoto_json.get("custom_image_dpi", 300)

        # 处理同时有自定义KB和DPI的情况
        if custom_kb and custom_dpi:
            # 为所有输出路径添加DPI信息
            for key in output_paths:
                output_paths[key]["path"] += f"_{custom_dpi}dpi.{format}"
            # 为标准图像添加KB信息
            output_paths["standard"]["path"] = output_paths["standard"]["path"].replace(
                f".{format}", f"_{custom_kb}kb.{format}"
            )

            # 调整标准图像大小并保存
            resize_image_to_kb(
                result_image_standard,
                output_paths["standard"]["path"],
                custom_kb,
                dpi=custom_dpi,
            )
            # 保存高清图像和排版图像
            save_image_dpi_to_bytes(
                result_image_hd, output_paths["hd"]["path"], dpi=custom_dpi
            )
            if result_image_layout is not None:
                save_image_dpi_to_bytes(
                    result_image_layout, output_paths["layout"]["path"], dpi=custom_dpi
                )

            return output_paths

        # 只有自定义DPI的情况
        elif custom_dpi:
            for key in output_paths:
                # 保存所有图像，使用自定义DPI
                # 如果只换底，则不保存排版图像
                if key == "layout" and result_image_layout is None:
                    continue
                output_paths[key]["path"] += f"_{custom_dpi}dpi.{format}"
                save_image_dpi_to_bytes(
                    locals()[f"result_image_{key}"],
                    output_paths[key]["path"],
                    dpi=custom_dpi,
                )

            return output_paths

        # 只有自定义KB的情况
        elif custom_kb:
            output_paths["standard"]["path"] += f"_{custom_kb}kb.{format}"
            output_paths["hd"]["path"] += f".{format}"
            for key in output_paths:
                if key == "layout" and result_image_layout is None:
                    continue
                output_paths[key]["path"] += f".{format}"
                
                # 只调整标准图像大小
                resize_image_to_kb(
                    result_image_standard,
                    output_paths["standard"]["path"],
                    custom_kb,
                    dpi=300,
                )
                
                # 保存高清图像和排版图像
                save_image_dpi_to_bytes(
                    result_image_hd, output_paths["hd"]["path"], dpi=300
                )
                if result_image_layout is not None:
                    save_image_dpi_to_bytes(
                        result_image_layout, output_paths["layout"]["path"], dpi=300
                    )

            return output_paths
        # 没有自定义设置
        else: 
            output_paths["standard"]["path"] += f".{format}"
            output_paths["hd"]["path"] += f".{format}"
            output_paths["layout"]["path"] += f".{format}"
            
            # 保存所有图像
            save_image_dpi_to_bytes(
                result_image_standard, output_paths["standard"]["path"], dpi=300
            )
            save_image_dpi_to_bytes(
                result_image_hd, output_paths["hd"]["path"], dpi=300
            )
            if result_image_layout is not None:
                save_image_dpi_to_bytes(
                    result_image_layout, output_paths["layout"]["path"], dpi=300
                )
                
            return output_paths
            

    @staticmethod
    def _prepare_ai_input_rgb(image, background_rgb=(255, 255, 255)):
        """Prepare the exact RGB image shown in AI input preview and sent to provider.

        Hivision's matting/background pipeline works with OpenCV-style BGR/BGRA arrays,
        while Gradio Image, PIL Image.fromarray, and the AI provider payload expect
        RGB/RGBA semantics.  If alpha is still present, flatten it on a safe white
        background before encoding so transparent matting areas cannot be rendered as
        the blue/zero-filled color carried in RGB channels.
        """
        if image is None:
            return None

        arr = np.asarray(image)
        if arr.ndim != 3 or arr.shape[2] < 3:
            return np.asarray(arr, dtype=np.uint8)

        arr = np.asarray(arr, dtype=np.uint8)
        channels = arr.shape[2]

        # If alpha exists this is still an OpenCV/Hivision BGRA image. Composite first,
        # then convert to RGB. Keeping RGBA through Image.fromarray/Gradio can expose
        # stale color values in fully transparent pixels as a blue preview/background.
        if channels == 4:
            alpha = arr[:, :, 3:4].astype(np.float32) / 255.0
            rgb = cv2.cvtColor(arr[:, :, :3], cv2.COLOR_BGR2RGB).astype(np.float32)
            background = np.empty_like(rgb, dtype=np.float32)
            background[:, :] = background_rgb
            return np.clip(rgb * alpha + background * (1.0 - alpha), 0, 255).astype(np.uint8)

        rgb_candidate = cv2.cvtColor(arr[:, :, :3], cv2.COLOR_BGR2RGB)

        # _render_background returns BGR for normal color modes.  A few upstream/plugin
        # paths may already return RGB; avoid a second swap when the image has the
        # common ID-photo blue background in RGB order.  This is intentionally narrow:
        # prefer the documented Hivision/OpenCV BGR path unless the edge background is
        # clearly RGB-blue.
        edge_pixels = np.concatenate(
            [arr[0, :, :3], arr[-1, :, :3], arr[:, 0, :3], arr[:, -1, :3]],
            axis=0,
        ).astype(np.int16)
        median_color = np.median(edge_pixels, axis=0)
        looks_rgb_blue = median_color[2] > median_color[0] + 30 and median_color[2] > median_color[1] + 30
        looks_bgr_blue = median_color[0] > median_color[2] + 30 and median_color[0] > median_color[1] + 30
        if looks_rgb_blue and not looks_bgr_blue:
            return arr[:, :, :3].copy()

        return rgb_candidate

    # Backward-compatible alias for older callers/tests; AI code should use
    # _prepare_ai_input_rgb so alpha flattening is explicit.
    _bgr_like_to_rgb = _prepare_ai_input_rgb

    @staticmethod
    def _decoded_image_to_rgb(image):
        """Convert cv2.imdecode BGR/BGRA output into RGB/RGBA for Gradio display."""
        if image is None:
            return None
        arr = np.asarray(image)
        if arr.ndim != 3 or arr.shape[2] < 3:
            return arr
        if arr.shape[2] == 4:
            return cv2.cvtColor(arr, cv2.COLOR_BGRA2RGBA)
        return cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)

    def _run_ai_enhance_preview(
        self,
        result_image_hd,
        language,
        enable_ai_enhance=False,
        ai_consent=False,
        ai_mode="repair",
        ai_template_name=AI_BACKGROUND_TEMPLATE_DEFAULT,
    ):
        template_defaults = {
            "background_template": AI_BACKGROUND_TEMPLATE_DEFAULT,
            "outfit": AI_OUTFIT_TEMPLATE_DEFAULT,
        }
        effective_template_name = None
        if ai_mode in template_defaults:
            effective_template_name = (ai_template_name or template_defaults[ai_mode]).strip()

        if not enable_ai_enhance:
            return (
                gr.update(value=None),
                gr.update(value=None),
                gr.update(value=LOCALES["ai_enhance"][language]["disabled_status"], visible=True),
            )

        if not ai_consent:
            return (
                gr.update(value=None),
                gr.update(value=None),
                gr.update(value=LOCALES["ai_enhance"][language]["consent_required_status"], visible=True),
            )

        try:
            ai_input_image = self._prepare_ai_input_rgb(result_image_hd)
            image_base64 = bytes_2_base64(save_image_dpi_to_bytes(ai_input_image, None, 300))
            result = self.ai_enhance_service.enhance(
                AIEnhanceRequest(
                    input_image_base64=image_base64,
                    mode=ai_mode,
                    consent=ai_consent,
                    template_name=effective_template_name,
                    return_base64=True,
                    client_id="webui",
                )
            )
        except AIEnhanceValidationError as exc:
            return (
                gr.update(value=ai_input_image),
                gr.update(value=None),
                gr.update(value=f"{LOCALES['ai_enhance'][language]['failed_status']}: {exc.message}", visible=True),
            )
        except Exception as exc:
            return (
                gr.update(value=ai_input_image if 'ai_input_image' in locals() else None),
                gr.update(value=None),
                gr.update(value=f"{LOCALES['ai_enhance'][language]['failed_status']}: {exc}", visible=True),
            )

        status_summary = self._format_ai_enhance_status(result, language)

        preview_image = None
        if result.status and not result.metadata.fallback_used and result.image_base64:
            preview_image = self._decoded_image_to_rgb(base64_2_numpy(result.image_base64))

        return (
            gr.update(value=ai_input_image),
            gr.update(value=preview_image),
            gr.update(value=status_summary, visible=True),
        )

    def _format_ai_enhance_status(self, result, language):
        metadata = result.metadata
        base_label = (
            LOCALES["ai_enhance"][language]["success_status"]
            if result.status
            else LOCALES["ai_enhance"][language]["fallback_status"]
        )
        parts = [
            base_label,
            LOCALES["ai_enhance"][language]["wait_hint"],
            f"provider={metadata.provider}",
            f"mode={metadata.mode}",
            f"template={getattr(metadata, 'template_name', None) or 'none'}",
            f"latency={metadata.latency_ms}ms",
            LOCALES["ai_enhance"][language]["validation_pass_label"]
            if metadata.validation_passed
            else LOCALES["ai_enhance"][language]["validation_fail_label"],
        ]
        if metadata.mode == "outfit":
            parts.append(LOCALES["ai_enhance"][language]["outfit_notice_status"])
            parts.append(f"mask_edit={getattr(metadata, 'mask_edit', False)}")
            parts.append(f"crop_edit={getattr(metadata, 'crop_edit', False)}")
            parts.append(f"face_protected={getattr(metadata, 'face_protected', False)}")
            color_guard = getattr(metadata, 'color_guard_passed', None)
            if color_guard is not None:
                parts.append(f"color_guard_passed={color_guard}")
            protected_delta = getattr(metadata, 'protected_region_delta', None)
            if protected_delta is not None:
                parts.append(f"protected_region_delta={protected_delta:.2f}")
        if metadata.request_id:
            parts.append(f"request_id={metadata.request_id[:8]}")
        if metadata.estimated_cost is not None:
            parts.append(f"estimated_cost={metadata.estimated_cost}")
        if metadata.fallback_used:
            parts.append(LOCALES["ai_enhance"][language]["fallback_output_not_shown_status"])
            if metadata.error_code == "RATE_LIMITED":
                parts.append(LOCALES["ai_enhance"][language]["rate_limited_status"])
            elif metadata.error_code == "TOO_MANY_CONCURRENT_REQUESTS":
                parts.append(LOCALES["ai_enhance"][language]["concurrency_limited_status"])
            elif metadata.error_code == "COLOR_CAST_DETECTED":
                parts.append(LOCALES["ai_enhance"][language]["color_cast_status"])
            else:
                parts.append(f"fallback={metadata.fallback_reason or 'unknown'}")
        if metadata.error_code:
            parts.append(f"error={metadata.error_code}")
        if metadata.validation_warnings:
            parts.append(f"warnings={';'.join(metadata.validation_warnings[:2])}")
        if result.message:
            parts.append(f"message={result.message}")
        return " | ".join(parts)

    def _create_response(
        self,
        result_image_standard,
        result_image_hd,
        result_image_standard_png,
        result_image_hd_png,
        result_layout_image_gr,
        result_image_template_gr,
        result_image_template_accordion_gr,
        ai_input_preview_image_gr,
        ai_output_preview_image_gr,
        ai_status_text_gr,
    ):
        """创建响应"""
        response = [
            result_image_standard,
            result_image_hd,
            result_image_standard_png,
            result_image_hd_png,
            result_layout_image_gr,
            result_image_template_gr,
            result_image_template_accordion_gr,
            gr.update(visible=False),
            ai_input_preview_image_gr,
            ai_output_preview_image_gr,
            ai_status_text_gr,
        ]

        return response

    def _create_error_response(self, language):
        """创建错误响应"""
        return [gr.update(value=None) for _ in range(4)] + [
            gr.update(value=None, visible=False),
            gr.update(value=None, visible=False),
            gr.update(visible=False),
            gr.update(
                value=LOCALES["size_mode"][language]["custom_size_eror"], visible=True
            ),
            gr.update(value=None),
            gr.update(value=None),
            gr.update(value=LOCALES["ai_enhance"][language]["disabled_status"], visible=True),
        ]
