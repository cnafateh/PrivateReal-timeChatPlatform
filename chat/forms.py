from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=False, help_text="Optional. Used for your Gravatar avatar; not shown on your profile.")

    username = forms.CharField(
        label="Username",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Choose a username",
                "autocomplete": "username",
                "autofocus": True,
            }
        ),
    )

    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Create a password",
                "autocomplete": "new-password",
            }
        ),
    )

    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Repeat your password",
                "autocomplete": "new-password",
            }
        ),
    )

    class Meta:
        model = User

        fields = (
            "username",
            "email",
            "password1",
            "password2",
        )

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.fields["username"].help_text = (
            "Letters, numbers and @/./+/-/_ only."
        )

        self.fields["password1"].help_text = (
            "Use at least 8 characters and avoid common passwords."
        )

        self.fields["password2"].help_text = (
            "Enter the same password again."
        )

class ProfileForm(forms.Form):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(max_length=254, required=False, help_text="Private. Used for Gravatar when enabled.")
    phone = forms.CharField(max_length=32, required=False, help_text="International format, e.g. +989121234567. Not verified.")
    show_phone = forms.BooleanField(required=False, label="Show my phone number to signed-in users")
    use_gravatar = forms.BooleanField(required=False, label="Use Gravatar when no photo is uploaded",
                                     help_text="Loads an image from Gravatar using a hash of your email address.")
    avatar = forms.FileField(required=False, widget=forms.FileInput(attrs={"accept":"image/png,image/jpeg,image/webp,image/gif"}),
                             help_text="PNG, JPEG, WebP or GIF, up to 5 MB.")
    remove_avatar = forms.BooleanField(required=False, label="Remove uploaded photo")

    def __init__(self, *args, profile, **kwargs):
        initial = {field: getattr(profile.user, field) for field in ("first_name", "last_name", "email")}
        initial.update({field: getattr(profile, field) for field in ("phone", "show_phone", "use_gravatar")})
        super().__init__(*args, initial=initial, **kwargs)

    def clean_phone(self):
        import re
        import unicodedata
        value = self.cleaned_data["phone"]
        value = "".join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in value)
        value = re.sub(r"[\s().-]", "", value)
        if value and not re.fullmatch(r"\+[1-9][0-9]{6,14}", value):
            raise forms.ValidationError("Enter a phone number with country code, e.g. +989121234567.")
        return value

    def clean_avatar(self):
        import io
        import warnings
        from django.core.files.base import ContentFile
        from PIL import Image, ImageOps, UnidentifiedImageError
        from .services import MAX_FILE_SIZE

        upload = self.cleaned_data["avatar"]
        if not upload:
            return None
        if not 0 < upload.size <= MAX_FILE_SIZE:
            raise forms.ValidationError("Photos must be non-empty and no larger than 5 MB.")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(upload) as image:
                    if image.format not in {"PNG", "JPEG", "GIF", "WEBP"} or image.width * image.height > 20_000_000:
                        raise ValueError
                    image = ImageOps.exif_transpose(image)
                    image.thumbnail((512, 512))
                    clean = Image.new("RGBA", image.size)
                    clean.paste(image.convert("RGBA"))
                    output = io.BytesIO()
                    clean.save(output, "PNG")
            return ContentFile(output.getvalue(), name="avatar.png")
        except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise forms.ValidationError("Choose a valid PNG, JPEG, WebP or GIF photo up to 20 megapixels.")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("avatar") and cleaned.get("remove_avatar"):
            self.add_error("remove_avatar", "Choose either a new photo or removal, not both.")
        return cleaned
