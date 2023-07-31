odoo.define('images_to_webp.website_sale_cart', function (require) {
    require('website_sale.cart');

    var publicWidget = require('web.public.widget');
    var timeout;

    publicWidget.registry.websiteSaleCartLink.include({
        _onMouseEnter: function (ev) {
            let self = this;
            self.hovered = true;
            clearTimeout(timeout);
            $(this.selector).not(ev.currentTarget).popover('hide');
            timeout = setTimeout(function () {
                if (!self.hovered || $('.mycart-popover:visible').length) {
                    return;
                }
                self._popoverRPC = $.get("/shop/cart", {
                    type: 'popover',
                }).then(function (data) {
                    const popover = Popover.getInstance(self.$el[0]);
                    popover._config.content = $(data);
                    popover.setContent(popover.getTipElement());
                    self.$el.popover("show");
                    $('.popover').on('mouseleave', function () {
                        self.$el.trigger('mouseleave');
                    });
                    self.cartQty = +$(data).find('.o_wsale_cart_quantity').text();
                    sessionStorage.setItem('website_sale_cart_quantity', self.cartQty);
                    self._updateCartQuantityText();
                });
            }, 300);
        },
    })
});