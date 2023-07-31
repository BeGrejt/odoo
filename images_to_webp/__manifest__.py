# -*- coding: utf-8 -*-
{
        "name": "WebP Image Optimizer",
        "summary": "WebP Image Optimizer",
        "description": """
		Install dependencies:
		`pip3 install webp`
		`pip3 install cssselect`
	""",
        'author': "Erpswiss",
        "website": "erpswiss.com",
        "category": "Website",
        "version": "16.0.2.2",
        "sequence": 1,
        'license': 'OPL-1',
        "depends": ['website'],
        "data": [
                'views/views.xml',
                ],
        'images': [
                'static/description/banner.png',
                'static/description/banner.jpg',
                ],
        "external_dependencies": {
                "python": [
                        "webp",
                        "cssselect",
                        "lxml"
                        ],
                },
        "assets": {
                'web_editor.assets_wysiwyg': [
                        "/images_to_webp/static/src/js/script.js",
                        ],
                'web.assets_frontend_lazy': [
                        "/images_to_webp/static/src/js/popover.js",
                        ],
                'web.assets_frontend': [
                        "/images_to_webp/static/src/scss/style.scss",
                        ],
                },
        "application": True,
        'installable': True,
        'auto_install': False,
        "support": "support@erpswiss.com",
        "price": 50,
        "currency": "EUR",
        }
