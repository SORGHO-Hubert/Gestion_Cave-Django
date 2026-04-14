import csv
from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.db.models import F, Sum
from io import BytesIO

# Imports PDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A6, A4
from reportlab.platypus import SimpleDocTemplate, Table

# Tes modèles et formulaires
from .models import Produit, Vente, Notification, Categorie, HistoriqueStock
from .forms import ProduitForm, SignupForm, CategorieForm
import json
from django.db import transaction
from django.contrib.auth.decorators import login_required
from .models import Produit, Vente, LigneVente, Notification

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
def valider_vente(request):
    # On accepte le POST pour traiter les données du panier
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            nom_client = data.get('client', 'Client Anonyme')
            articles = data.get('articles', [])

            if not articles:
                return JsonResponse({'success': False, 'message': 'Le panier est vide'})

            with transaction.atomic():
                # 1. Création de la vente globale
                v = Vente.objects.create(
                    nom_client=nom_client,
                    utilisateur=request.user,
                    total_general=0
                )

                total_final = 0
                for item in articles:
                    p = get_object_or_404(Produit, pk=item['id'])
                    q = int(item['qte'])

                    if p.quantite < q:
                        return JsonResponse({'success': False, 'message': f'Stock insuffisant pour {p.nom}'})

                    sous_total = p.prix * q

                    # 2. Création de la ligne de vente
                    LigneVente.objects.create(
                        vente=v,
                        produit=p,
                        quantite=q,
                        prix_unitaire=p.prix,
                        sous_total=sous_total
                    )

                    # 3. Mise à jour du stock
                    p.quantite -= q
                    p.save()

                    # --- CORRECTION NOTIFICATION ---
                    # On crée la notification sans le champ 'utilisateur'
                    Notification.objects.create(
                        message=f"Vente de {q} {p.nom} à {nom_client}"
                    )

                    total_final += sous_total

                # 4. Enregistrement du total final
                v.total_general = total_final
                v.save()

            return JsonResponse({'success': True, 'vente_id': v.id})

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    # Si ce n'est pas du POST, on renvoie une erreur claire
    return JsonResponse({'success': False, 'message': 'Erreur : La requête doit être de type POST'})

def succes_vente(request, vente_id):
    return render(request, 'gestion/recu_vente.html', {'vente': get_object_or_404(Vente, id=vente_id)})

def generer_recu_pdf(request, vente_id):
    v = get_object_or_404(Vente, id=vente_id)
    response = HttpResponse(content_type='application/pdf')
    p = canvas.Canvas(response, pagesize=A6)
    p.drawString(20, 380, f"REÇU - {v.produit.nom}")
    p.drawString(20, 310, f"Total: {v.prix_total} FCFA")
    p.showPage()
    p.save()
    return response

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