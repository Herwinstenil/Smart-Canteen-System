from django import forms
from .models import MenuItem

class OrderForm(forms.Form):
    def __init__(self, *args, **kwargs):
        menu_items = kwargs.pop('menu_items', [])
        super().__init__(*args, **kwargs)

        for item in menu_items:
            self.fields[f'item_{item.id}'] = forms.IntegerField(
                label='',
                min_value=0,
                initial=0,
                required=False
            )
