import csv
from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.db.models import F, Sum
from io import BytesIO

from reportlab.lib.pagesizes import A6, A4
from reportlab.platypus import SimpleDocTemplate, Table

# Tes modèles et formulaires
from .models import Produit, Vente, Notification, Categorie, HistoriqueStock
from .forms import ProduitForm, SignupForm, CategorieForm
import json
from django.db import transaction
from django.contrib.auth.decorators import login_required
from .models import Produit, Vente, LigneVente, Notification
from django.shortcuts import render

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A6

import os
from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from .models import Vente

# --- SÉCURITÉ ---
def est_admin(user):
    return user.is_superuser

# --- DASHBOARD ---
# Dans views.py, cherche la fonction dashboard
@login_required
def dashboard(request):
    # REMPLACE 'prix_total' PAR 'total_general'
    total_ca = Vente.objects.aggregate(Sum('total_general'))['total_general__sum'] or 0

    context = {
        'total_ca': total_ca,
        'nb_ventes': Vente.objects.count(),
        # ... reste du context
    }
    return render(request, 'gestion/dashboard.html', context)

# --- PRODUITS (CRUD) ---
@login_required
def liste_produits(request):
    query = request.GET.get('search')
    cat_id = request.GET.get('categorie')
    statut = request.GET.get('statut')
    produits = Produit.objects.all()
    if query: produits = produits.filter(nom__icontains=query)
    if cat_id: produits = produits.filter(categorie_id=cat_id)
    if statut == 'ok': produits = produits.filter(quantite__gt=F('seuil_alerte'))
    elif statut == 'alert': produits = produits.filter(quantite__lte=F('seuil_alerte'), quantite__gt=0)
    elif statut == 'rupture': produits = produits.filter(quantite=0)
    return render(request, 'gestion/liste_produits.html', {'produits': produits, 'categories': Categorie.objects.all()})


@login_required
def ajouter_produit(request):
    if request.method == "POST":
        form = ProduitForm(request.POST)
        if form.is_valid():
            p = form.save()
            HistoriqueStock.objects.create(
                produit=p,
                type_action='AJOUT',
                quantite_changee=p.quantite,
                utilisateur=request.user
            )
            # AU LIEU DE REDIRIGER, ON RECHARGE LA PAGE VIDE AVEC UN MESSAGE
            return redirect('ajouter_produit')

    return render(request, 'gestion/ajouter_produit.html', {'form': ProduitForm()})

@login_required
def modifier_produit(request, pk):
    p = get_object_or_404(Produit, pk=pk)
    old_q = p.quantite
    if request.method == "POST":
        form = ProduitForm(request.POST, instance=p)
        if form.is_valid():
            p = form.save()
            if old_q != p.quantite:
                diff = p.quantite - old_q
                HistoriqueStock.objects.create(produit=p, type_action='ENTREE' if diff > 0 else 'SORTIE', quantite_changee=abs(diff), utilisateur=request.user)
            return redirect('liste_produits')
    return render(request, 'gestion/modifier_produit.html', {'form': ProduitForm(instance=p), 'produit': p})

@login_required
def supprimer_produit(request, pk):
    get_object_or_404(Produit, pk=pk).delete()
    return redirect('liste_produits')

# --- CATÉGORIES ---
@login_required
def liste_categories(request):
    return render(request, 'gestion/liste_categories.html', {'categories': Categorie.objects.all()})

@login_required
def ajouter_categorie(request):
    if request.method == "POST":
        CategorieForm(request.POST).save()
        return redirect('liste_categories')
    return render(request, 'gestion/ajouter_categorie.html', {'form': CategorieForm()})

@login_required
def modifier_categorie(request, pk):
    c = get_object_or_404(Categorie, pk=pk)
    if request.method == "POST":
        CategorieForm(request.POST, instance=c).save()
        return redirect('liste_categories')
    return render(request, 'gestion/modifier_categorie.html', {'form': CategorieForm(instance=c), 'categorie': c})

@login_required
def supprimer_categorie(request, pk):
    get_object_or_404(Categorie, pk=pk).delete()
    return redirect('liste_categories')

# --- VENTES & REÇUS ---
@login_required
def page_vente(request):
    return render(request, 'gestion/effectuer_vente.html', {'produits': Produit.objects.filter(quantite__gt=0)})

def get_produit_details(request, pk):
    p = get_object_or_404(Produit, pk=pk)
    return JsonResponse({'nom': p.nom, 'prix': float(p.prix), 'quantite': p.quantite})


@login_required
@transaction.atomic
def valider_vente(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            articles = data.get('articles', [])
            nom_client = data.get('client', 'Client Anonyme')

            if not articles:
                return JsonResponse({'success': False, 'message': 'Le panier est vide'})

            # 1. Création de la vente en base de données
            vente = Vente.objects.create(
                nom_client=nom_client,
                utilisateur=request.user,
                total_general=0
            )

            total_vente = 0
            for item in articles:
                produit = Produit.objects.get(id=item['id'])
                qte = int(item['qte'])
                prix_u = float(item['prix'])
                sous_total = prix_u * qte

                # Créer la ligne de détail
                LigneVente.objects.create(
                    vente=vente,
                    produit=produit,
                    quantite=qte,
                    prix_unitaire=prix_u,
                    sous_total=sous_total
                )

                # Mise à jour du stock
                produit.quantite -= qte
                produit.save()
                total_vente += sous_total

            # 2. Sauvegarde du total final
            vente.total_general = total_vente
            vente.save()

            # --- LA NOUVEAUTÉ : GÉNÉRATION ET STOCKAGE DU REÇU ---
            try:
                # On appelle la fonction de création du fichier PDF
                enregistrer_recu_physique(vente)
            except Exception as e:
                # On print l'erreur dans le terminal pour débugger sans bloquer la vente
                print(f"Erreur lors de l'enregistrement du PDF : {e}")

            return JsonResponse({'success': True, 'vente_id': vente.id})

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': 'Méthode non autorisée'})

def succes_vente(request, vente_id):
    return render(request, 'gestion/recu_vente.html', {'vente': get_object_or_404(Vente, id=vente_id)})



def generer_recu_pdf(request, vente_id):
    # 1. On récupère la vente
    vente = get_object_or_404(Vente, id=vente_id)

    # 2. On définit le chemin où le fichier devrait être stocké
    nom_fichier = f"recu_vente_{vente.id}.pdf"
    chemin_pdf = os.path.join(settings.BASE_DIR, 'reçus', nom_fichier)

    # 3. On vérifie si le fichier existe physiquement
    if os.path.exists(chemin_pdf):
        # Si le fichier existe, on le sert directement
        return FileResponse(open(chemin_pdf, 'rb'), content_type='application/pdf')
    else:
        # Si le fichier n'existe pas (ex: ancienne vente), on peut soit lever une erreur 404
        # Soit appeler la fonction de création pour le générer maintenant
        try:
            from .views import enregistrer_recu_physique  # Assure-toi que la fonction est accessible
            nouveau_chemin = enregistrer_recu_physique(vente)
            return FileResponse(open(nouveau_chemin, 'rb'), content_type='application/pdf')
        except Exception:
            raise Http404("Le reçu PDF n'a pas pu être trouvé ou généré.")

# --- RAPPORTS & EXPORTS ---
@login_required
def rapport_ventes(request):
    ventes = Vente.objects.all().order_by('-date_vente')
    return render(request, 'gestion/rapport_ventes.html', {'ventes': ventes})

@login_required
def exporter_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="inventaire.csv"'
    response.write(u'\ufeff'.encode('utf8'))
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Nom', 'Stock', 'Prix'])
    for p in Produit.objects.all(): writer.writerow([p.nom, p.quantite, p.prix])
    return response

@login_required
def exporter_pdf(request):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    data = [['Nom', 'Stock']]
    for p in Produit.objects.all(): data.append([p.nom, str(p.quantite)])
    doc.build([Table(data)])
    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf')

# --- NOTIFICATIONS ---
def liste_notifications(request):
    # On utilise 'notifs' ici pour que ça corresponde au dictionnaire plus bas
    notifs = Notification.objects.all().order_by('-date_creation')

    # Dès qu'on ouvre la page, on marque tout comme lu
    Notification.objects.filter(lu=False).update(lu=True)

    # Maintenant 'notifs' est reconnu par Python
    return render(request, 'gestion/notifications.html', {'notifs': notifs})


def marquer_notification_lue(request, notif_id):
    n = get_object_or_404(Notification, id=notif_id)
    n.lu = True
    n.save()
    return redirect('liste_notifications')

@login_required
def supprimer_notification(request, notif_id):
    get_object_or_404(Notification, id=notif_id).delete()
    return redirect('liste_notifications')

# --- STATS & HISTORIQUE ---
@login_required
def statistiques(request):
    return render(request, 'gestion/statistiques.html', {'total_produits': Produit.objects.count()})

@login_required
def historique_stock(request):
    return render(request, 'gestion/historique.html', {'historique': HistoriqueStock.objects.all().order_by('-date_action')})

# --- AUTH ---
def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            User.objects.create_user(username=form.cleaned_data['username'], password=form.cleaned_data['password1'])
            return redirect('login')
    return render(request, 'registration/signup.html', {'form': SignupForm()})

@login_required
def verifier_patron_inventaire(request):
    if request.method == 'POST' and authenticate(username=request.user.username, password=request.POST.get('password')):
        return redirect('liste_produits')
    return render(request, 'gestion/verif_password.html')
  # Assure-toi que l'import est là


def historique_ventes(request):
    # On récupère toutes les ventes par date décroissante
    ventes = Vente.objects.all().order_by('-date_vente')

    # Récupération des filtres
    nom_client = request.GET.get('nom_client')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')

    # Application des filtres si remplis
    if nom_client:
        ventes = ventes.filter(nom_client__icontains=nom_client)

    if date_debut and date_fin:
        ventes = ventes.filter(date_vente__date__range=[date_debut, date_fin])

    # Calcul du CA Total pour l'affichage
    ca_total = ventes.aggregate(total=Sum('total_general'))['total'] or 0

    return render(request, 'gestion/historique.html', {
        'ventes': ventes,
        'ca_total': ca_total,
        'nom_client': nom_client
    })


def enregistrer_recu_physique(vente):
    # 1. Définir le chemin du dossier (racine_du_projet/reçus/)
    dossier_reçus = os.path.join(settings.BASE_DIR, 'reçus')

    # Créer le dossier s'il n'existe pas encore
    if not os.path.exists(dossier_reçus):
        os.makedirs(dossier_reçus)

    # 2. Nom du fichier basé sur l'ID de la vente
    nom_fichier = f"recu_vente_{vente.id}.pdf"
    chemin_complet = os.path.join(dossier_reçus, nom_fichier)

    # 3. Génération du PDF avec ReportLab
    c = canvas.Canvas(chemin_complet, pagesize=A6)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20, 380, "TICKET DE CAISSE")

    c.setFont("Helvetica", 10)
    c.drawString(20, 360, f"Client : {vente.nom_client}")
    c.drawString(20, 345, f"Date : {vente.date_vente.strftime('%d/%m/%Y %H:%M')}")
    c.drawString(20, 330, f"Vendu par : {vente.utilisateur.username}")

    c.line(20, 320, 280, 320)

    # Liste des articles
    y = 300
    for ligne in vente.lignes.all():
        c.drawString(20, y, f"{ligne.produit.nom} x{ligne.quantite}")
        c.drawRightString(280, y, f"{ligne.sous_total} FCFA")
        y -= 15

    c.line(20, y, 280, y)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20, y - 20, "TOTAL GENERAL")
    c.drawRightString(280, y - 20, f"{vente.total_general} FCFA")

    c.showPage()
    c.save()

    return chemin_complet

