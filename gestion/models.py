from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

# --- CATEGORIE ET PRODUIT (Inchangés) ---
class Categorie(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.nom

class Produit(models.Model):
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    prix = models.DecimalField(max_digits=10, decimal_places=2)
    quantite = models.IntegerField(default=0)
    categorie = models.ForeignKey(Categorie, on_delete=models.SET_NULL, null=True, blank=True)
    date_ajout = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    seuil_alerte = models.IntegerField(default=5)
    image = models.ImageField(upload_to='produits/', blank=True, null=True)

    def __str__(self): return self.nom

    @property
    def statut_stock(self):
        if self.quantite == 0: return "RUPTURE"
        return "ALERT" if self.quantite <= self.seuil_alerte else "OK"

# --- NOUVELLE STRUCTURE DE VENTE (Multi-Produits) ---

class Vente(models.Model):
    nom_client = models.CharField(max_length=100)
    date_vente = models.DateTimeField(auto_now_add=True)
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE)
    total_general = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"Vente {self.id} - {self.nom_client}"

class LigneVente(models.Model):
    """ Représente chaque produit à l'intérieur d'une vente """
    vente = models.ForeignKey(Vente, related_name='lignes', on_delete=models.CASCADE)
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE)
    quantite = models.PositiveIntegerField()
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    sous_total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantite} x {self.produit.nom} (Vente #{self.vente.id})"

# --- HISTORIQUE ET NOTIFICATION (Inchangés) ---
class HistoriqueStock(models.Model):
    # ... garde ton code actuel ici ...
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE)
    type_action = models.CharField(max_length=20)
    quantite_changee = models.IntegerField(default=0)
    date_action = models.DateTimeField(auto_now_add=True)
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

class Notification(models.Model):
    message = models.CharField(max_length=255)
    date_creation = models.DateTimeField(auto_now_add=True)
    lu = models.BooleanField(default=False)