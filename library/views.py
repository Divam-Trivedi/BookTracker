import requests, random
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Book, UserBook, UserLibrary
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseNotFound
from random import sample
from django.core.files.storage import default_storage
import uuid
from django.contrib.auth import authenticate, login, logout, get_user_model

def home(request):
    return render(request, 'library/home.html')

def surprise_start(request):
    return render(request, 'library/surprise_start.html')

import logging
from django.contrib import messages
logger = logging.getLogger(__name__)

@login_required
def add_to_library(request, book_id):
    if request.method != 'POST':
        return redirect('home')

    logger.info(f"add_to_library called: book_id={book_id} user={request.user}")

    # 1) Try DB first (covers surprise page when showing DB books)
    book = Book.objects.filter(google_books_id=book_id).first()

    # 2) If not in DB, try session (covers search page flow)
    if not book:
        book_info = request.session.get('book_info', {}).get(book_id)
        if book_info:
            cover = book_info.get('thumbnail') or book_info.get('cover_url') or ''
            book, created = Book.objects.get_or_create(
                google_books_id=book_id,
                defaults={
                    'title': book_info.get('title', 'No title'),
                    'authors': ', '.join(book_info.get('authors', [])),
                    'description': book_info.get('description', ''),
                    'thumbnail': cover,
                    'cover_url': cover,
                    'categories': ', '.join(book_info.get('categories', [])) if book_info.get('categories') else '',
                }
            )

    # 3) If still not found, try Google Books API (covers "global" surprise books)
    if not book:
        url = f"https://www.googleapis.com/books/v1/volumes/{book_id}"
        try:
            resp = requests.get(url, timeout=8)
        except requests.RequestException as e:
            logger.warning("Google Books API request failed: %s", e)
            messages.error(request, "Could not reach Google Books API. Try again.")
            return redirect('surprise_result')

        if resp.status_code == 200:
            data = resp.json()
            info = data.get('volumeInfo', {})
            image_links = info.get('imageLinks', {}) or {}
            cover_url = (
                image_links.get('extraLarge') or
                image_links.get('large') or
                image_links.get('medium') or
                image_links.get('thumbnail') or
                ''
            )

            # create the Book in DB
            book, created = Book.objects.get_or_create(
                google_books_id=book_id,
                defaults={
                    'title': info.get('title', 'No title'),
                    'authors': ', '.join(info.get('authors', []) or []),
                    'description': info.get('description', ''),
                    'thumbnail': cover_url,
                    'cover_url': cover_url,
                    'categories': ', '.join(info.get('categories', []) or []),
                }
            )
        else:
            logger.info("Google Books API returned %s for id=%s", resp.status_code, book_id)
            messages.error(request, "Could not find book details to add.")
            return redirect('surprise_result')

    # 4) Now create the user-book relation
    userbook, created = UserBook.objects.get_or_create(user=request.user, book=book)
    if created:
        messages.success(request, f'Added "{book.title}" to your library.')
    else:
        messages.info(request, f'"{book.title}" is already in your library.')

    return redirect('my_library')

    

def search_books(request):
    query = request.GET.get('q', '').strip()
    results = []
    book_info_dict = {}

    if query:
        url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=20"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            for item in data.get('items', []):
                info = item.get('volumeInfo', {})
                image_links = info.get('imageLinks', {})
                cover_url = (
                    image_links.get('extraLarge') or
                    image_links.get('large') or
                    image_links.get('medium') or
                    image_links.get('thumbnail') or
                    ''
                )
                if 'zoom=1' in cover_url:
                    cover_url = cover_url.replace('zoom=1', 'zoom=3')

                book_id = item.get('id')
                book_data = {
                    'title': info.get('title', 'No title'),
                    'authors': info.get('authors', ['Unknown author']),
                    'description': info.get('description', ''),
                    'thumbnail': cover_url,
                    'categories': info.get('categories', ['Unknown genre']),
                }
                results.append({
                    'id': book_id,
                    'title': book_data['title'],
                    'authors': ', '.join(book_data['authors']),
                    'cover_url': cover_url,
                    'categories': ', '.join(info.get('categories', ['Unknown genre'])),
                })

                # Save each book's data in a dict using its ID
                book_info_dict[book_id] = book_data

    # Store the book_info_dict in session
    request.session['book_info'] = book_info_dict

    return render(request, 'library/search_results.html', {
        'query': query,
        'results': results,
    })


def surprise_result(request):
    random_terms = ['fiction', 'adventure', 'science', 'history', 'romance', 'fantasy', 'mystery', 'art', 'biography']
    query = random.choice(random_terms)

    url = f'https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=40'
    response = requests.get(url)
    data = response.json()
    books = data.get('items', [])

    if not books:
        return render(request, 'library/surprise_result.html', {'book': None})

    # Pick a random item
    chosen_item = random.choice(books)
    info = chosen_item.get('volumeInfo', {})
    image_links = info.get('imageLinks', {})

    cover_url = (
        image_links.get('extraLarge') or
        image_links.get('large') or
        image_links.get('medium') or
        image_links.get('thumbnail') or
        ''
    )

    google_id = chosen_item.get('id')  # ✅ correct Google Books ID

    # Prepare book data in the same format as search_books
    book_data = {
        'title': info.get('title', 'Unknown Title'),
        'authors': info.get('authors', ['Unknown Author']),
        'description': info.get('description', ''),
        'thumbnail': cover_url,
        'categories': info.get('categories', ['Unknown']),
    }

    # Store in session so add_to_library can use it
    session_books = request.session.get('book_info', {})
    session_books[google_id] = book_data
    request.session['book_info'] = session_books

    # Prepare the object for the template
    book = {
        'id': google_id,  # ✅ same key name as search results
        'title': book_data['title'],
        'authors': ', '.join(book_data['authors']),
        'categories': ', '.join(book_data['categories']),
        'cover_url': cover_url,
    }

    return render(request, 'library/surprise_result.html', {'book': book})



@login_required
def my_library(request):
    user_books = UserBook.objects.filter(user=request.user).select_related('book')
    current_filter = request.GET.get('status', 'all')
    if current_filter != 'all':
        user_books = user_books.filter(status=current_filter)
    return render(request, 'library/my_library.html', {
        'user_books': user_books,
        'current_filter': current_filter,
    })

def update_status(request, pk):
    book = get_object_or_404(UserBook, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        book.status = new_status
        book.save()
    
    current_filter = request.GET.get('status', '')
    if current_filter:
        return redirect(f"{reverse('my_library')}?status={current_filter}")
    return redirect('my_library')

def remove_book(request, pk):
    book = get_object_or_404(UserBook, pk=pk)
    """
    Deletes a UserBook object and redirects the user to their library page. If there was a status filter on the library page,
    the user is redirected with the same filter. Otherwise, the user is redirected to the my_library page.
    """
    if request.method == 'POST':
        book.delete()
    
    current_filter = request.GET.get('status', '')
    if current_filter:
        return redirect(f"{reverse('my_library')}?status={current_filter}")
    return redirect('my_library')

def explore_home(request):
    return render(request, 'library/explore_home.html')

def get_suggestions(request):
    mode = request.GET.get('mode')

    # All books in user's library
    user_books = UserBook.objects.filter(user=request.user)
    user_book_ids = user_books.values_list('book_id', flat=True)
    user_genres = Book.objects.filter(id__in=user_book_ids).values_list('genre', flat=True)

    if mode == 'taste':
        # Suggest books with similar genres, not already in their library
        suggestions = Book.objects.filter(
            genre__in=user_genres
        ).exclude(id__in=user_book_ids).distinct()[:5]

    elif mode == 'different':
        # Suggest books from genres the user hasn't read yet
        suggestions = Book.objects.exclude(
            genre__in=user_genres
        ).exclude(id__in=user_book_ids).distinct()[:5]

    else:
        suggestions = []

    return render(request, 'library/suggestions.html', {
        'suggestions': suggestions,
        'mode': mode
    })

def select_book(request, book_id):
    selected = request.session.get('selected_books', [])
    if book_id not in selected:
        selected.append(book_id)
    request.session['selected_books'] = selected
    return redirect('search_books')

def clear_selection(request):
    request.session['selected_books'] = []
    return redirect('search_books')

@login_required
def explore_similar(request):
    # Get current book context (from session or user profile)
    current_book = request.session.get('current_book', None)

    if current_book:
        categories = current_book.get('categories', [])
        query_term = random.choice(categories) if categories else current_book.get('title', 'fiction')
    else:
        # fallback if user has no current book
        query_term = 'fiction'

    # Call Google Books API
    url = f'https://www.googleapis.com/books/v1/volumes?q={query_term}&maxResults=20'
    response = requests.get(url)
    data = response.json()
    books = data.get('items', [])

    recommended_books = []

    for item in books:
        info = item.get('volumeInfo', {})
        image_links = info.get('imageLinks', {})
        cover_url = (
            image_links.get('extraLarge') or
            image_links.get('large') or
            image_links.get('medium') or
            image_links.get('thumbnail') or
            ''
        )

        recommended_books.append({
            'id': item.get('id'),
            'title': info.get('title', 'Unknown Title'),
            'author': ', '.join(info.get('authors', ['Unknown Author'])),
            'cover_url': cover_url,
        })

    # Optional: randomly pick 5 books to display
    recommended_books = random.sample(recommended_books, min(5, len(recommended_books)))

    return render(request, 'library/explore_similar.html', {'recommended_books': recommended_books})

@login_required
def explore_different(request):
    """
    Recommend books outside of the user's current reading categories.
    """

    # Define a broad list of possible genres
    all_genres = ['fiction', 'adventure', 'science', 'history', 'romance',
                  'fantasy', 'mystery', 'art', 'biography', 'self-help', 'poetry', 'philosophy']

    # Get current book context (from session or user profile)
    current_book = request.session.get('current_book', None)

    # Exclude current book categories
    excluded_genres = current_book.get('categories', []) if current_book else []
    possible_genres = [g for g in all_genres if g not in excluded_genres]

    # Pick a random genre outside current reading
    query_term = random.choice(possible_genres) if possible_genres else random.choice(all_genres)

    # Call Google Books API
    url = f'https://www.googleapis.com/books/v1/volumes?q={query_term}&maxResults=20'
    response = requests.get(url)
    data = response.json()
    books = data.get('items', [])

    recommended_books = []

    for item in books:
        info = item.get('volumeInfo', {})
        image_links = info.get('imageLinks', {})
        cover_url = (
            image_links.get('extraLarge') or
            image_links.get('large') or
            image_links.get('medium') or
            image_links.get('thumbnail') or
            ''
        )

        recommended_books.append({
            'id': item.get('id'),
            'title': info.get('title', 'Unknown Title'),
            'author': ', '.join(info.get('authors', ['Unknown Author'])),
            'cover_url': cover_url,
        })

    # Optional: randomly pick 5 books to display
    recommended_books = random.sample(recommended_books, min(5, len(recommended_books)))

    return render(request, 'library/explore_different.html', {'recommended_books': recommended_books})

@login_required
def add_custom_book(request):
    if request.method == 'POST':
        title = request.POST.get('title').strip()
        authors = request.POST.get('authors', '').strip()
        categories = request.POST.get('categories', '').strip()
        status = request.POST.get('status', 'Not Started')

        # Handle image upload
        cover_url = ''
        uploaded_file = request.FILES.get('cover_image')
        if uploaded_file:
            filename = default_storage.save(f'covers/{uploaded_file.name}', uploaded_file)
            cover_url = default_storage.url(filename)

        # Create Book (google_books_id can be blank for custom books)
        book, created = Book.objects.get_or_create(
            google_books_id=f"CUSTOM-{uuid.uuid4()}",
            defaults={
                'title': title,
                'authors': authors or 'Unknown Author',
                'categories': categories or 'Unknown Genre',
                'thumbnail': cover_url,
                'description': ''
            }
        )

        # Link to user
        UserBook.objects.get_or_create(
            user=request.user,
            book=book,
            defaults={'status': status}
        )

        messages.success(request, f'"{title}" has been added to your library.')
        return redirect('my_library')

    return redirect('home')

User = get_user_model()


def custom_login_view(request):
    """
    Handles both social links (they are anchors to provider) and manual email/password login.
    The login form uses input name="login" (email or username) and name="password".
    We try authenticate() first with the raw value; if it looks like an email and fails,
    we try find a user with that email and authenticate using their username.
    """
    if request.method == "POST":
        # debug prints are fine when developing
        # print("Login POST request received", request.POST)

        login_val = request.POST.get('login') or request.POST.get('username') or ''
        password = request.POST.get('password') or ''

        user = None
        if login_val and password:
            # First try direct authenticate (works if login_val is username)
            user = authenticate(request, username=login_val, password=password)

            # If not found and login_val looks like an email, try lookup by email
            if user is None and '@' in login_val:
                try:
                    u = User.objects.get(email__iexact=login_val)
                    user = authenticate(request, username=u.username, password=password)
                except User.DoesNotExist:
                    user = None

        if user:
            # authenticate() sets proper backend attribute so login() will work
            login(request, user)
            return redirect('home')
        else:
            # show helpful error
            return render(request, 'account/login.html', {'error': 'Invalid credentials. Please check email/username and password.'})

    # GET
    return render(request, 'account/login.html')


def custom_logout_view(request):
    if request.method == 'POST':
        logout(request)
        return redirect('home')
    # optional confirmation GET view
    return render(request, 'account/logout.html')


def custom_signup_view(request):
    """
    Create a user and log them in. Use backend argument because we call login()
    on a newly-created user (not returned by authenticate()).
    """
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password1 = request.POST.get("password1", "")
        password2 = request.POST.get("password2", "")

        # Validation
        if password1 != password2:
            return render(request, "account/signup.html", {"error": "Passwords do not match", "username": username, "email": email})

        if not username:
            return render(request, "account/signup.html", {"error": "Username is required", "email": email})

        if User.objects.filter(username=username).exists():
            return render(request, "account/signup.html", {"error": "Username already taken", "email": email})

        if User.objects.filter(email=email).exists():
            return render(request, "account/signup.html", {"error": "Email already registered", "username": username})

        # Create user
        user = User.objects.create_user(username=username, email=email, password=password1)

        # Auto-login after signup: must specify backend (because we didn't authenticate())
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        return redirect("home")

    # GET
    return render(request, "account/signup.html")
'''
Book.objects.create(title="The Life", authors="Haruki", cover_url="/static/images/sample_book_cover.jpg")
'''