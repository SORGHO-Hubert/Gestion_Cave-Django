from django.contrib import admin
from .models import Categorie, Produit, Vente, LigneVente, Notification

# Ajoute cette ligne pour voir les catégories dans l'admin
admin.site.register(Categorie)

# Tu peux aussi ajouter les autres pour tout gérer d'ici
admin.site.register(Produit)
admin.site.register(Vente)
admin.site.register(Notification)