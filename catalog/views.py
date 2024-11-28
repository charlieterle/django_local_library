from django.shortcuts import render
from .models import Book, Author, BookInstance, Genre
from django.views import generic

def index(request):
    """View function for home page of site"""

    num_books = Book.objects.count()
    num_instances = BookInstance.objects.count()
    num_authors = Author.objects.count()

    # Available books (status = 'a')
    num_instances_available = BookInstance.objects.filter(status__exact='a').count()

    # Books with the word 'history' in title
    num_harry_potter_books = Book.objects.filter(title__icontains='harry potter').count()

    # Genres with the word fragment 'histor' in the genre name
    num_history_genres = Genre.objects.filter(name__icontains='histor').count()

    context = {
        'num_books' : num_books,
        'num_instances' : num_instances,
        'num_authors' : num_authors,
        'num_instances_available' : num_instances_available,
        'num_harry_potter_books' : num_harry_potter_books,
        'num_history_genres' : num_history_genres,
    }

    return render(request, 'index.html', context=context)

class BookListView(generic.ListView):
    model = Book
    paginate_by = 3

class BookDetailView(generic.DetailView):
    model = Book

class AuthorListView(generic.ListView):
    model = Author
    paginate_by = 3

class AuthorDetailView(generic.DetailView):
    model = Author