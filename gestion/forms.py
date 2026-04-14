from django import forms
from .models import Produit, Categorie
from hcaptcha.fields import hCaptchaField


captcha = hCaptchaField()

class CategorieForm(forms.ModelForm):
    class Meta:
        model = Categorie
        fields = ['nom', 'description']
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Nom de la catégorie',
                'required': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 
                'placeholder': 'Description de la catégorie',
                'rows': 3
            }),
        }


class ProduitForm(forms.ModelForm):
    class Meta:
        model = Produit
        fields = ['nom', 'description', 'prix', 'quantite', 'categorie', 'seuil_alerte', 'image']
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Nom du produit',
                'required': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 
                'placeholder': 'Description du produit',
                'rows': 3
            }),
            'prix': forms.NumberInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Prix en FCFA',
                'step': '0.01',
                'min': '0'
            }),
            'quantite': forms.NumberInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Quantité en stock',
                'min': '0'
            }),
            'categorie': forms.Select(attrs={'class': 'form-control'}),
            'seuil_alerte': forms.NumberInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Seuil d\'alerte',
                'min': '1',
                'value': '5'
            }),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def clean_quantite(self):
        quantite = self.cleaned_data.get('quantite')
        if quantite is not None and quantite < 0:
            raise forms.ValidationError("La quantité ne peut pas être négative.")
        return quantite

    def clean_prix(self):
        prix = self.cleaned_data.get('prix')
        if prix is not None and prix <= 0:
            raise forms.ValidationError("Le prix doit être supérieur à 0.")
        return prix


class VenteForm(forms.Form):
    produit = forms.ModelChoiceField(
        queryset=Produit.objects.filter(quantite__gt=0),
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'produit-select'})
    )
    quantite = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Quantité',
            'id': 'quantite-input'
        })
    )
    nom_client = forms.CharField(
        max_length=100,
        initial="Client Anonyme",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Nom du client'
        })
    )
    captcha = hCaptchaField()


class RechercheForm(forms.Form):
    recherche = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Rechercher un produit...',
            'autocomplete': 'off'
        })
    )
    categorie = forms.ModelChoiceField(
        queryset=Categorie.objects.all(),
        required=False,
        empty_label="Toutes les catégories",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    statut_stock = forms.ChoiceField(
        choices=[('', 'Tous'), ('OK', 'En stock'), ('ALERT', 'Stock bas'), ('RUPTURE', 'Rupture')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    captcha = hCaptchaField()


class SignupForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nom d\'utilisateur'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Adresse email'
        })
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Mot de passe'
        })
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirmer le mot de passe'
        })
    )
    captcha = hCaptchaField()