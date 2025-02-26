from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import (ListView, CreateView, UpdateView,
                                  DetailView, DeleteView)
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import ModelFormMixin

from .forms import PostForm, CommentForm
from .models import Post, Category, Comment

User = get_user_model()


class PostListView(ListView):
    model = Post
    template_name = 'blog/index.html'
    paginate_by = 10

    def get_queryset(self):
        return Post.objects.filter(
            is_published=True, category__is_published=True,
            location__is_published=True, pub_date__lte=timezone.now()
        ).order_by('-pub_date').annotate(comment_count=Count('comments'))


class PostDetailView(DetailView):
    model = Post
    template_name = 'blog/detail.html'

    def get_object(self, queryset=None):
        post = get_object_or_404(Post, pk=self.kwargs['post_id'])
        if (post.author == self.request.user
            or (post.is_published and post.category.is_published
                and post.location.is_published)):
            return post
        else:
            raise Http404

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = CommentForm()
        context['comments'] = self.object.comments.select_related('author')
        return context


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        username = self.object.author.username
        return reverse('blog:profile', args=[username])


class AuthorPostMixin(LoginRequiredMixin, SingleObjectMixin):
    def dispatch(self, request, *args, **kwargs):
        post = self.get_object()
        if post.author != request.user:
            return redirect(reverse('blog:post_detail',
                                    kwargs={'post_id': post.pk}))
        return super().dispatch(request, *args, **kwargs)


class PostEditView(AuthorPostMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'

    def get_object(self, queryset=None):
        return get_object_or_404(Post, pk=self.kwargs.get('post_id'))

    def get_success_url(self):
        return reverse('blog:post_detail', kwargs={'post_id': self.object.pk})


class PostDeleteView(AuthorPostMixin, ModelFormMixin, DeleteView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'

    def get_object(self, queryset=None):
        return get_object_or_404(Post, pk=self.kwargs['post_id'])

    def get_success_url(self):
        return reverse('blog:profile',
                       kwargs={'username': self.object.author.username})


class CategoryPostsListView(ListView):
    model = Post
    template_name = 'blog/category.html'
    paginate_by = 10

    def get_category(self):
        category = get_object_or_404(Category,
                                     slug=self.kwargs.get('category_slug'),
                                     is_published=True)

        return category

    def get_queryset(self):
        category = self.get_category()

        return (
            category.posts
            .filter(is_published=True, pub_date__lte=timezone.now(),
                    category__is_published=True)
            .order_by('-pub_date')
            .annotate(comment_count=Count('comments'))
            .select_related('category', 'location', 'author')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = self.get_category()
        return context


class CommentCreateView(LoginRequiredMixin, CreateView):
    model = Comment
    form_class = CommentForm
    template_name = 'blog/comment.html'

    def form_valid(self, form):
        post_id = self.kwargs.get('post_id')
        form.instance.post = get_object_or_404(Post, pk=post_id)
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('blog:post_detail',
                       kwargs={'post_id': self.kwargs.get('post_id')})


class AuthorCommentMixin(LoginRequiredMixin, SingleObjectMixin):
    def dispatch(self, request, *args, **kwargs):
        comment = self.get_object()
        if comment.author != request.user:
            return redirect(reverse('blog:post_detail',
                                    kwargs={'post_id': comment.post.pk}))
        return super().dispatch(request, *args, **kwargs)


class CommentEditView(AuthorCommentMixin, UpdateView):
    model = Comment
    form_class = CommentForm
    template_name = 'blog/comment.html'

    def get_object(self, queryset=None):
        return get_object_or_404(Comment, pk=self.kwargs.get('comment_id'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['post_id'] = self.kwargs.get('post_id')
        return context

    def get_success_url(self):
        return reverse('blog:post_detail',
                       kwargs={'post_id': self.kwargs.get('post_id')})


class CommentDeleteView(AuthorCommentMixin, DeleteView):
    model = Comment
    template_name = 'blog/comment.html'

    def get_object(self, queryset=None):
        post_id = self.kwargs.get('post_id')
        comment_id = self.kwargs.get('comment_id')
        return get_object_or_404(Comment, pk=comment_id, post_id=post_id)

    def get_success_url(self):
        return reverse('blog:post_detail',
                       kwargs={'post_id': self.kwargs.get('post_id')})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class UserDetailView(ListView):
    model = Post
    template_name = 'blog/profile.html'
    paginate_by = 10

    def get_queryset(self):
        author = (
            get_object_or_404(User, username=self.kwargs.get('username'))
        )
        queryset = (author.posts.annotate(comment_count=Count('comments'))
                    .order_by('-pub_date'))

        if self.request.user != author:
            queryset = queryset.filter(pub_date__lte=timezone.now())

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = (
            get_object_or_404(User, username=self.kwargs.get('username'))
        )
        return context


class EditProfileView(LoginRequiredMixin, UpdateView):
    class EditProfileForm(forms.ModelForm):
        class Meta:
            model = User
            fields = ('username', 'email', 'first_name', 'last_name')


    form_class = EditProfileForm
    model = User
    template_name = 'blog/user.html'

    def get_object(self, queryset=None):
        return get_object_or_404(User, username=self.request.user.username)

    def get_success_url(self):
        return reverse('blog:profile',
                       kwargs={'username': self.object.username})
