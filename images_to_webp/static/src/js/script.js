odoo.define('images_to_webp.file_selector', function (require) {
    const {IMAGE_MIMETYPES, IMAGE_EXTENSIONS} = require('@web_editor/components/media_dialog/file_selector');

    IMAGE_MIMETYPES.push('image/webp');
    IMAGE_EXTENSIONS.push('.webp');

    return {
        IMAGE_MIMETYPES,
        IMAGE_EXTENSIONS
    };
});

odoo.define('images_to_webp.editor', function (require) {
    var EditorMenuBar = require('web_editor.snippet.editor');

    EditorMenuBar.SnippetsMenu.include({
        init: function (parent, options) {
            var self = this;
            var res = self._super.apply(self, arguments);

            this.$body.find('picture').each(function (_, elem) {
                $(elem).replaceWith($(elem).find('img'));
            });

            return res;
        }
    });

    return EditorMenuBar;
});