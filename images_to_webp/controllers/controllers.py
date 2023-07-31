# -*- coding: utf-8 -*-
import odoo
from odoo import http, _
from odoo.http import request
from odoo.tools.image import image_process
from odoo.addons.web.controllers.binary import Binary
from odoo.addons.web_editor.controllers.main import Web_Editor
from odoo.exceptions import UserError
import base64, io, webp
from PIL import Image, ImageSequence
from ..models.ir_ui_view import check_webp_support


class Binary(Binary):
    @http.route()
    def content_image(self, xmlid = None, model = 'ir.attachment', id = None, field = 'raw',
                      filename_field = 'name', filename = None, mimetype = None, unique = False,
                      download = False, width = 0, height = 0, crop = False, access_token = None,
                      nocache = False, **kwargs):
        return self._content_image(xmlid = xmlid, model = model, id = id, field = field,
                                   filename_field = filename_field, unique = unique, filename = filename,
                                   mimetype = mimetype, nocache = nocache,
                                   download = download, width = width, height = height, crop = crop,
                                   quality = int(kwargs.get('quality', 0)), access_token = access_token)

    def _content_image(self, xmlid = None, model = 'ir.attachment', id = None, field = 'datas',
                       filename_field = 'name', unique = None, filename = None, mimetype = None,
                       download = None, width = 0, height = 0, crop = False, quality = 0, access_token = None,
                       nocache = False):
        webp_support = check_webp_support(request)
        convert_back_to_png = False
        w = width
        h = height

        try:
            record = request.env['ir.binary']._find_record(xmlid, model, id and int(id), access_token)
            stream = request.env['ir.binary']._get_image_stream_from(
                    record, field, filename = filename, filename_field = filename_field,
                    mimetype = mimetype, width = 0, height = 0, crop = False,
                    )

            if stream and stream.mimetype == "image/webp":
                if not webp_support:
                    convert_back_to_png = True
            else:
                if width or height or crop:
                    stream = request.env['ir.binary']._get_image_stream_from(
                            record, field, filename = filename, filename_field = filename_field,
                            mimetype = mimetype, width = int(width), height = int(height), crop = crop,
                            )
        except UserError as exc:
            if download:
                raise request.not_found() from exc

            if (int(width), int(height)) == (0, 0):
                width, height = odoo.tools.image_guess_size_from_field_name(field)
            record = request.env.ref('web.image_placeholder').sudo()
            stream = request.env['ir.binary']._get_image_stream_from(
                    record, 'raw', width = int(width), height = int(height), crop = crop,
                    )

        send_file_kwargs = {'as_attachment': download}
        if unique:
            send_file_kwargs['immutable'] = True
            send_file_kwargs['max_age'] = http.STATIC_CACHE_LONG
        if nocache:
            send_file_kwargs['max_age'] = None

        if convert_back_to_png:
            webp_data = webp.WebPData.from_buffer(stream.read())
            arr = webp_data.decode()
            source_image = Image.fromarray(arr, 'RGBA')

            if w or h:
                source_image.thumbnail((w, h))

            convert_to_png = io.BytesIO()
            source_image.save(convert_to_png, 'PNG')

            stream.type = 'data'
            stream.data = convert_to_png.getvalue()
            stream.size = len(stream.data)

        return stream.get_response(**send_file_kwargs)


class WebP(http.Controller):
    def _convert_image_to_webp(self, img_data, quality, webp_arr = False, format = None):
        source_image = webp_arr and img_data or Image.open(io.BytesIO(img_data))
        format = format or source_image.format

        if format == "GIF":
            fps = 10

            if webp_arr:
                pics = source_image
            else:
                pics = []

                for frame in ImageSequence.Iterator(source_image):
                    pics.append(webp.WebPPicture.from_pil(frame.copy()))

            enc_opts = webp.WebPAnimEncoderOptions.new()
            enc = webp.WebPAnimEncoder.new(pics[0].ptr.width, pics[0].ptr.height, enc_opts)
            config = webp.WebPConfig.new(lossless = True, quality = quality)

            for i, pic in enumerate(pics):
                t = round((i * 1000) / fps)
                enc.encode_frame(pic, t, config)

            end_t = round((len(pics) * 1000) / fps)
            anim_data = enc.assemble(end_t)

            return io.BytesIO(anim_data.buffer()).getvalue()
        else:
            pic = webp.WebPPicture.from_pil(source_image.convert("RGBA"))
            config = webp.WebPConfig.new(preset = webp.WebPPreset.PHOTO, quality = quality)

            return pic.encode(config).buffer()

    def _webp_to_buffer(self, img_data, quality, width, height, return_non_webp = False):
        webp_data = webp.WebPData.from_buffer(img_data)

        arrs = []
        pilmode = 'RGBA'
        fps = None

        if pilmode == 'RGBA':
            color_mode = webp.WebPColorMode.RGBA
        elif pilmode == 'RGBa':
            color_mode = webp.WebPColorMode.rgbA
        elif pilmode == 'RGB':
            color_mode = webp.WebPColorMode.RGBA
        else:
            raise webp.WebPError('unsupported color mode: ' + pilmode)

        dec_opts = webp.WebPAnimDecoderOptions.new(use_threads = True, color_mode = color_mode)
        dec = webp.WebPAnimDecoder.new(webp_data, dec_opts)
        eps = 1e-7

        for arr, frame_end_time in dec.frames():
            if pilmode == 'RGB':
                arr = arr[:, :, 0:3]
            if fps is None:
                arrs.append(arr)
            else:
                while len(arrs) * (1000 / fps) + eps < frame_end_time:
                    arrs.append(arr)

        if len(arrs) > 1:
            source_images = [Image.fromarray(arr, pilmode).convert(mode = 'RGBA') for arr in arrs]

            if width or height:
                for s_img in source_images:
                    s_img.thumbnail((width, height))

            if return_non_webp:
                convert_to_gif = io.BytesIO()
                source_images[0].save(convert_to_gif, "PNG", save_all = True, append_images = source_images[1:],
                                      loop = 0)
                img_data = convert_to_gif.getvalue()
            else:
                pics = [webp.WebPPicture.from_pil(img) for img in source_images]
                img_data = self._convert_image_to_webp(pics, quality, webp_arr = True, format = "GIF")
        else:
            arr = webp_data.decode()
            source_image = Image.fromarray(arr, 'RGBA')

            if width or height:
                source_image.thumbnail((width, height))

            if return_non_webp:
                convert_to_png = io.BytesIO()
                source_image.save(convert_to_png, 'PNG')
                img_data = convert_to_png.getvalue()
            else:
                pic = webp.WebPPicture.from_pil(source_image)
                config = webp.WebPConfig.new(preset = webp.WebPPreset.PHOTO, quality = quality)

                img_data = pic.encode(config).buffer()

        return return_non_webp and img_data or base64.b64encode(img_data)

    @http.route([
            '/webp/image',
            '/webp/image/<string:xmlid>',
            '/webp/image/<string:xmlid>/<string:filename>',
            '/webp/image/<string:xmlid>/<int:width>x<int:height>',
            '/webp/image/<string:xmlid>/<int:width>x<int:height>/<string:filename>',
            '/webp/image/<string:model>/<int:id>/<string:field>',
            '/webp/image/<string:model>/<int:id>/<string:field>/<string:filename>',
            '/webp/image/<string:model>/<int:id>/<string:field>/<int:width>x<int:height>',
            '/webp/image/<string:model>/<int:id>/<string:field>/<int:width>x<int:height>/<string:filename>',
            '/webp/image/<int:id>',
            '/webp/image/<int:id>/<string:filename>',
            '/webp/image/<int:id>/<int:width>x<int:height>',
            '/webp/image/<int:id>/<int:width>x<int:height>/<string:filename>',
            '/webp/image/<int:id>-<string:unique>',
            '/webp/image/<int:id>-<string:unique>/<string:filename>',
            '/webp/image/<int:id>-<string:unique>/<int:width>x<int:height>',
            '/webp/image/<int:id>-<string:unique>/<int:width>x<int:height>/<string:filename>'
            ], type = 'http', auth = "public")
    def content_image(self, xmlid = None, model = 'ir.attachment', id = None, field = 'raw',
                      filename_field = 'name', filename = None, mimetype = None, unique = False,
                      download = False, width = 0, height = 0, crop = False, access_token = None,
                      nocache = False, **kwargs):
        return self._content_image(xmlid = xmlid, model = model, id = id, field = field,
                                   filename_field = filename_field, unique = unique, filename = filename,
                                   mimetype = mimetype, nocache = nocache,
                                   download = download, width = width, height = height, crop = crop,
                                   quality = int(kwargs.get('quality', 0)), access_token = access_token)

    def _content_image(self, xmlid = None, model = 'ir.attachment', id = None, field = 'datas',
                       filename_field = 'name', unique = None, filename = None, mimetype = None,
                       download = None, width = 0, height = 0, crop = False, quality = 0, access_token = None,
                       nocache = False):
        webp_support = check_webp_support(request)
        is_webp = False
        change_headers = False

        try:
            attachment = request.env['ir.binary']._find_record(xmlid, model, id and int(id), access_token)
            stream = request.env['ir.binary']._get_image_stream_from(
                    attachment, field, filename = filename, filename_field = filename_field,
                    mimetype = mimetype, width = 0, height = 0, crop = False,
                    )

            if stream and stream.mimetype == "image/webp":
                is_webp = True

        except UserError as exc:
            if download:
                raise request.not_found() from exc

            if (int(width), int(height)) == (0, 0):
                width, height = odoo.tools.image_guess_size_from_field_name(field)
            record = request.env.ref('web.image_placeholder').sudo()
            stream = request.env['ir.binary']._get_image_stream_from(
                    record, 'raw', width = int(width), height = int(height), crop = crop,
                    )

        image_base64 = base64.b64encode(stream.read())

        if stream.mimetype != 'image/svg+xml':
            try:
                Image.open(io.BytesIO(base64.b64decode(image_base64)))
            except Exception:
                is_webp = True

        if not is_webp:
            image_base64 = base64.b64encode(image_process(stream.read(), size = (int(width), int(height)), crop = crop,
                                                          quality = quality))
        else:
            if webp_support:
                width = int(width or height) or 0
                height = int(height or width) or 0
                quality = quality or int(request.session.get('webp_image_quality', 95)) or 95

                image_base64 = self._webp_to_buffer(base64.b64decode(image_base64), quality, width, height)

        img_data = base64.b64decode(image_base64)

        send_file_kwargs = {'as_attachment': download}

        if unique:
            send_file_kwargs['immutable'] = True
            send_file_kwargs['max_age'] = http.STATIC_CACHE_LONG
        if nocache:
            send_file_kwargs['max_age'] = None

        if stream.mimetype != 'image/svg+xml':
            width = width or height or 0
            height = height or width or 0

            if webp_support:
                quality = quality or int(request.session.get('webp_image_quality', 95)) or 95

                if not is_webp:
                    img_data = self._convert_image_to_webp(img_data, quality)
            else:
                if is_webp:
                    img_data = self._webp_to_buffer(img_data, quality, width, height, return_non_webp = True)

            change_headers = True

        stream.type = 'data'
        stream.data = img_data
        stream.size = len(stream.data)

        response = stream.get_response(**send_file_kwargs)

        if change_headers:
            headers = response.headers

            for key, item in enumerate(headers):
                if item[0] == 'Content-Type':
                    headers[key] = ('Content-Type', webp_support and 'image/webp' or 'image/png')
                if item[0] == 'Content-Length':
                    headers[key] = ('Content-Length', stream.size)

        return response


class Web_Editor(Web_Editor):
    def _attachment_create(self, name = '', data = False, url = False, res_id = False, res_model = 'ir.ui.view',
                           is_webp = False):
        """Create and return a new attachment."""
        if name.lower().endswith('.bmp'):
            # Avoid mismatch between content type and mimetype, see commit msg
            name = name[:-4]

        if not name and url:
            name = url.split("/").pop()

        if res_model != 'ir.ui.view' and res_id:
            res_id = int(res_id)
        else:
            res_id = False

        attachment_data = {
                'name': name,
                'public': res_model == 'ir.ui.view',
                'res_id': res_id,
                'res_model': res_model,
                }

        if data:
            attachment_data[is_webp and 'raw' or 'datas'] = data
        elif url:
            attachment_data.update({
                    'type': 'url',
                    'url': url,
                    })
        else:
            raise UserError(_("You need to specify either data or url to create an attachment."))

        attachment = request.env['ir.attachment'].create(attachment_data)
        return attachment

    @http.route('/web_editor/attachment/add_data', type = 'json', auth = 'user', methods = ['POST'], website = True)
    def add_data(self, name, data, is_image, quality = 0, width = 0, height = 0, res_id = False,
                 res_model = 'ir.ui.view', **kwargs):
        website = request.website
        webp_config = website and website.enable_webp_compress or False

        if webp_config:
            is_webp = False

            try:
                data = base64.b64decode(data)
                data = WebP._convert_image_to_webp(self, data, quality = quality or website.webp_image_quality or 95)
                data = base64.b64encode(data)
            except Exception:
                is_webp = True

            attachment = self._attachment_create(name = name, data = data, res_id = res_id, res_model = res_model,
                                                 is_webp = is_webp)
            result = attachment._get_media_info()

            name = name.split('.')[0]
            name += ".webp"
            attachment.name = name
            attachment.mimetype = "image/webp"

            return result
        else:
            return super(Web_Editor, self).add_data(name = name, data = data, is_image = is_image, quality = quality,
                                                    width = width,
                                                    height = height,
                                                    res_id = res_id, res_model = res_model, **kwargs)
