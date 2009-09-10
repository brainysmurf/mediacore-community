var OverTextManager = new Class({
	form: null,
	ots: [],

	initialize: function(form) {
		this.form = $(form);
		this.ots = this.form.getElements('input[type=text], textarea').map(function(el) {
			return new CustomOverText(el, {
				poll: true,
				pollInterval: 400
			});
		});
	}
});

var CustomOverText = new Class({
	Extends: OverText,
	
	getLabelElement: function() {
		var els = $$('label[for='+this.element.id+']');
		if (els.length > 0) {
			return els[0];
		} else {
			return undefined;
		}
	},

	modifyForm: function() {
		var oldParent = $(this.text.parentNode);
		var newParent = $(this.element.parentNode);
		oldParent.removeChild(this.text);
		this.text.inject(this.element, 'after');
		oldParent.destroy();
		newParent.removeClass('form-field');
		newParent.addClass('form-field-wide');
	},

	attach: function() {
		this.text = this.getLabelElement();
		if ($defined(this.text)) {
			// Element exists!
			this.modifyForm();
			this.text.addEvent('click', this.hide.pass(true, this))
			this.element.addEvents({
				focus: this.focus,
				blur: this.assert,
				change: this.assert
			}).store('OverTextDiv', this.text);
			window.addEvent('resize', this.reposition.bind(this));
			/* Sometimes there's a race condition that prevents the
			 * elements from getting displayed correctly (they're positioned
			 * too far up the page). This should reset them after 1 second. */
			this.assert.delay(1000, this);
			this.reposition.delay(1300, this);
		} else {
			// label element doesn't exist. fall back to
			// regular OverText behaviour and create one.
			parent();
		}
	}
});
