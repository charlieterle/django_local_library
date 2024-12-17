import datetime
import uuid

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Author, BookInstance, Book, Genre, Language

# Required to grant permissions needed to perform staff functions
from django.contrib.auth.models import Permission

from django.contrib.auth import get_user_model

from django.contrib.contenttypes.models import ContentType

User = get_user_model()

class AuthorListViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        number_of_authors = 13
        for author_id in range(number_of_authors):
            Author.objects.create(
                first_name=f'Charles {author_id}',
                last_name=f'Surname {author_id}',
            )

    def test_view_url_exists_at_desired_location(self):
        response = self.client.get('/catalog/authors/')
        self.assertEqual(response.status_code, 200)

    def test_view_url_accessible_by_name(self):
        response = self.client.get(reverse('authors'))
        self.assertEqual(response.status_code, 200)

    def test_view_uses_correct_template(self):
        response = self.client.get(reverse('authors'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'catalog/author_list.html')

    def test_pagination_is_ten(self):
        response = self.client.get(reverse('authors'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue('is_paginated' in response.context)
        self.assertTrue(response.context['is_paginated'] == True)
        self.assertEqual(len(response.context['author_list']), 10)

    def test_lists_all_authors(self):
        response = self.client.get(reverse('authors')+'?page=2')
        self.assertEqual(response.status_code, 200)
        self.assertTrue('is_paginated' in response.context)
        self.assertTrue(response.context['is_paginated'] == True)
        self.assertEqual(len(response.context['author_list']), 3)

class LoanedBookInstancesByUserListViewTest(TestCase):
    def setUp(self):
        test_user1 = User.objects.create_user(username='testuser1', password='helloworld')
        test_user2 = User.objects.create_user(username='testuser2', password='helloworld')
        test_user1.save()
        test_user2.save()

        test_author = Author.objects.create(first_name='Charles', last_name='Dieterle')
        test_language = Language.objects.create(name='Japanese')
        test_book = Book.objects.create(
            title='Book Title',
            summary='Very long book summary. Very, very long.',
            isbn='1234567890123',
            author=test_author,
            language=test_language
        )

        # Direct assignment of many-to-many types not allowed, so create genre separately
        # and use book.genre.set()
        Genre.objects.create(name='Fantasy')
        genre_objects_for_book = Genre.objects.all()
        test_book.genre.set(genre_objects_for_book)
        test_book.save()

        # Create Bookinstances
        number_of_book_copies = 30
        for book_copy in range(number_of_book_copies):
            return_date = timezone.localtime() + datetime.timedelta(days=book_copy%5)
            the_borrower = test_user1 if book_copy % 2 else test_user2
            status = 'm'
            BookInstance.objects.create(
                book=test_book,
                imprint='2042',
                due_back=return_date,
                borrower=the_borrower,
                status=status,
            )

    def test_redirect_if_not_logged_in(self):
        response = self.client.get(reverse('my-borrowed'))
        self.assertRedirects(response, '/accounts/login/?next=/catalog/mybooks/')

    def test_logged_in_uses_correct_template(self):
        # Log in the client
        self.client.login(username='testuser1', password='helloworld')
        response = self.client.get(reverse('my-borrowed'))

        # Check if our user is logged in
        self.assertEqual(str(response.context['user']), 'testuser1')
        self.assertEqual(response.status_code, 200)

        # Check we used correct template
        self.assertTemplateUsed(response, 'catalog/bookinstance_list_borrowed_user.html')

    def test_only_borrowed_books_in_list(self):
        self.client.login(username='testuser1', password='helloworld')
        response = self.client.get(reverse('my-borrowed'))

        # Check our user is logged in
        self.assertEqual(str(response.context['user']), 'testuser1')
        self.assertEqual(response.status_code, 200)

        # Check that initially we don't have any books in list (none on loan)
        self.assertTrue('bookinstance_list' in response.context)
        self.assertEqual(len(response.context['bookinstance_list']), 0)

        # Now change all books to be on loan
        books = BookInstance.objects.all()[:10]

        for book in books:
            book.status = 'o'
            book.save()

        # Check that now we have borrowed books in the list
        response = self.client.get(reverse('my-borrowed'))
        # Check our user is logged in
        self.assertEqual(str(response.context['user']), 'testuser1')
        # Check that we got a response "success"
        self.assertEqual(response.status_code, 200)

        self.assertTrue('bookinstance_list' in response.context)

        # Confirm all books belong to testuser1 and are on loan
        for book_item in response.context['bookinstance_list']:
            self.assertEqual(response.context['user'], book_item.borrower)
            self.assertEqual(book_item.status, 'o')

    def test_pages_ordered_by_due_date(self):
        # Change all books to be on loan
        for book in BookInstance.objects.all():
            book.status='o'
            book.save()

        self.client.login(username='testuser1', password='helloworld')
        response = self.client.get(reverse('my-borrowed'))

        # Check our user is logged in
        self.assertEqual(str(response.context['user']), 'testuser1')
        # Check that we got a response "success"
        self.assertEqual(response.status_code, 200)

        # Confirm that of the items, only 10 are displayed due to pagination.
        self.assertEqual(len(response.context['bookinstance_list']), 10)

        last_date = 0
        for book in response.context['bookinstance_list']:
            if last_date == 0:
                last_date = book.due_back
            else:
                self.assertTrue(last_date <= book.due_back)
                last_date = book.due_back

class RenewBookInstancesViewTest(TestCase):
    def setUp(self):
        test_user1 = User.objects.create_user(username='testuser1', password='helloworld')
        test_user2 = User.objects.create_user(username='testuser2', password='helloworld')
        test_user1.save()
        test_user2.save()

        # Give testuser2 permissions to renew books
        renew_permission = Permission.objects.get(name='Renew books for library users')
        view_loaned_books_permission = Permission.objects.get(name='View all loaned books from library')
        test_user2.user_permissions.add(renew_permission)
        test_user2.user_permissions.add(view_loaned_books_permission)
        test_user2.save()

        # Create a book
        test_author = Author.objects.create(first_name='John', last_name='Smith')
        test_language = Language.objects.create(name='Japanese')
        test_book = Book.objects.create(
            title='Book Title',
            summary='Book Summary',
            isbn='1234567890123',
            author=test_author,
            language=test_language,
        )

        Genre.objects.create(name='Fantasy')
        genre_objects_for_book = Genre.objects.all()
        test_book.genre.set(genre_objects_for_book)
        test_book.save()

        # Create a BookInstance object for testuser1
        return_date = datetime.date.today() + datetime.timedelta(days=5)
        self.test_bookinstance1 = BookInstance.objects.create(
            book=test_book,
            imprint='whatever',
            due_back=return_date,
            borrower=test_user1,
            status='o',
        )

        # Create a BookInstance objects for testuser2
        return_date = datetime.date.today() + datetime.timedelta(days=5)
        self.test_bookinstance2 = BookInstance.objects.create(
            book=test_book,
            imprint='whatever',
            due_back=return_date,
            borrower=test_user2,
            status='o',
        )

    def test_redirect_if_not_logged_in(self):
        response = self.client.get(
            reverse('renew-book-librarian', kwargs={'pk' : self.test_bookinstance1.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))

    def test_forbidden_if_logged_in_but_not_correct_permission(self):
        login = self.client.login(username='testuser1', password='helloworld')
        response = self.client.get(reverse('renew-book-librarian', kwargs={'pk' : self.test_bookinstance1.pk}))
        self.assertEqual(response.status_code, 403)

    def test_logged_in_with_permission_borrowed_book(self):
        login = self.client.login(username='testuser2', password='helloworld')
        response = self.client.get(reverse('renew-book-librarian', kwargs={'pk' : self.test_bookinstance2.pk}))
        self.assertEqual(response.status_code, 200)

    def test_logged_in_with_permission_another_users_borrowed_book(self):
        login = self.client.login(username='testuser2', password='helloworld')
        response = self.client.get(reverse('renew-book-librarian', kwargs={'pk' : self.test_bookinstance1.pk}))
        self.assertEqual(response.status_code, 200)

    def test_HTTP404_for_invalid_book_if_logged_in(self):
        test_uid = uuid.uuid4()
        login = self.client.login(username='testuser2', password='helloworld')
        response = self.client.get(reverse('renew-book-librarian', kwargs={'pk' : test_uid}))
        self.assertEqual(response.status_code, 404)

    def test_uses_correct_template(self):
        login = self.client.login(username='testuser2', password='helloworld')
        response = self.client.get(reverse('renew-book-librarian', kwargs={'pk' : self.test_bookinstance1.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'catalog/book_renew_librarian.html')

    def test_form_renewal_date_initially_has_date_three_weeks_in_future(self):
        login = self.client.login(username='testuser2', password='helloworld')
        response = self.client.get(reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}))
        self.assertEqual(response.status_code, 200)

        date_3_weeks_in_future = datetime.date.today() + datetime.timedelta(weeks=3)
        self.assertEqual(response.context['form'].initial['renewal_date'], date_3_weeks_in_future)

    def test_redirects_to_all_borrowed_book_list_on_success(self):
        login = self.client.login(username='testuser2', password='helloworld')
        valid_date_in_future = datetime.date.today() + datetime.timedelta(weeks=2)
        response = self.client.post(reverse('renew-book-librarian', kwargs={'pk':self.test_bookinstance1.pk,}), {'renewal_date':valid_date_in_future})
        self.assertRedirects(response, reverse('all-loaned'))

    def test_form_invalid_renewal_date_past(self):
        login = self.client.login(username='testuser2', password='helloworld')
        date_in_past = datetime.date.today() - datetime.timedelta(weeks=1)
        response = self.client.post(reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}), {'renewal_date': date_in_past})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'renewal_date', 'Invalid date - renewal in past')

    def test_form_invalid_renewal_date_future(self):
        login = self.client.login(username='testuser2', password='helloworld')
        invalid_date_in_future = datetime.date.today() + datetime.timedelta(weeks=5)
        response = self.client.post(reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}), {'renewal_date': invalid_date_in_future})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'renewal_date', 'Invalid date - renewal more than 4 weeks ahead')

class AuthorCreateViewTest(TestCase):
    def setUp(self):
        test_user1 = User.objects.create_user(username='testuser1', password='helloworld')
        test_user2 = User.objects.create_user(username='testuser2', password='helloworld')
        test_user1.save()
        test_user2.save()

        # Give test_user2 permission to create an author
        content_typeAuthor = ContentType.objects.get_for_model(Author)
        permAddAuthor = Permission.objects.get(
            codename='add_author',
            content_type=content_typeAuthor,
        )

        test_user2.user_permissions.add(permAddAuthor)
        test_user2.save()

        # Create an author 
        self.test_author = Author.objects.create(
            first_name='John',
            last_name='Smith',
            date_of_birth='1963-05-20',
            date_of_death='2024-03-04',
        )

    def test_forbidden_if_logged_in_but_not_correct_permission(self):
        login = self.client.login(username='testuser1', password='helloworld')
        response = self.client.get(reverse('author-create'))
        self.assertEqual(response.status_code, 403)

    def test_access_allowed_for_user_with_permission(self):
        login = self.client.login(username='testuser2', password='helloworld')
        response = self.client.get(reverse('author-create'))
        self.assertEqual(response.status_code, 200)

    def test_correct_template_used(self):
        login = self.client.login(username='testuser2', password='helloworld')
        response = self.client.get(reverse('author-create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'catalog/author_form.html')

    def test_redirects_on_successful_post(self):
        login = self.client.login(username='testuser2', password='helloworld')
        response = self.client.post(
            reverse('author-create'),
            {
                'first_name' : 'Charles',
                'last_name' : 'Dieterle', 
                'date_of_birth' : self.test_author.date_of_birth,
                'date_of_death' : self.test_author.date_of_death,
            }
        )
        self.assertRedirects(response, reverse('author-detail', kwargs={'pk' : 2}))
