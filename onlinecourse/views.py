
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import generic
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate
from .models import Course, Enrollment, Question, Choice, Submission
import logging

logger = logging.getLogger(__name__)


def registration_request(request):
    context = {}

    if request.method == 'GET':
        return render(
            request,
            'onlinecourse/user_registration_bootstrap.html',
            context
        )

    elif request.method == 'POST':
        username = request.POST['username']
        password = request.POST['psw']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']

        user_exist = User.objects.filter(username=username).exists()

        if not user_exist:
            user = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                password=password
            )
            login(request, user)
            return redirect("onlinecourse:index")

        context['message'] = "User already exists."
        return render(
            request,
            'onlinecourse/user_registration_bootstrap.html',
            context
        )


def login_request(request):
    context = {}

    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['psw']
        user = authenticate(username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')

        context['message'] = "Invalid username or password."
        return render(
            request,
            'onlinecourse/user_login_bootstrap.html',
            context
        )

    return render(
        request,
        'onlinecourse/user_login_bootstrap.html',
        context
    )


def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


def check_if_enrolled(user, course):
    if user.is_authenticated:
        return Enrollment.objects.filter(
            user=user,
            course=course
        ).exists()

    return False


class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.order_by('-total_enrollment')[:10]

        for course in courses:
            if user.is_authenticated:
                course.is_enrolled = check_if_enrolled(user, course)

        return courses


class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_detail_bootstrap.html'


def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    if user.is_authenticated and not check_if_enrolled(user, course):
        Enrollment.objects.create(
            user=user,
            course=course,
            mode='honor'
        )
        course.total_enrollment += 1
        course.save()

    return HttpResponseRedirect(
        reverse(
            viewname='onlinecourse:course_details',
            args=(course.id,)
        )
    )


def extract_answers(request):
    submitted_answers = []

    for key, value in request.POST.items():
        if key.startswith('choice_'):
            try:
                submitted_answers.append(int(value))
            except (TypeError, ValueError):
                continue

    return Choice.objects.filter(id__in=submitted_answers)


def submit(request, course_id):
    if request.method != 'POST':
        return HttpResponseRedirect(
            reverse('onlinecourse:course_details', args=(course_id,))
        )

    if not request.user.is_authenticated:
        return redirect('onlinecourse:login')

    course = get_object_or_404(Course, pk=course_id)

    enrollment = get_object_or_404(
        Enrollment,
        user=request.user,
        course=course
    )

    submission = Submission.objects.create(
        enrollment=enrollment
    )

    choices = extract_answers(request)

    # Save only choices belonging to questions in this course.
    valid_choices = choices.filter(question__course=course)
    submission.choices.set(valid_choices)

    return HttpResponseRedirect(
        reverse(
            'onlinecourse:exam_result',
            args=(course_id, submission.id)
        )
    )


def show_exam_result(request, course_id, submission_id):
    course = get_object_or_404(Course, pk=course_id)

    submission = get_object_or_404(
        Submission,
        id=submission_id,
        enrollment__course=course
    )

    choices = submission.choices.all()
    total_score = 0

    questions = course.question_set.all()

    for question in questions:
        correct_choices = question.choice_set.filter(
            is_correct=True
        )

        selected_choices = choices.filter(
            question=question
        )

        correct_ids = set(
            correct_choices.values_list('id', flat=True)
        )

        selected_ids = set(
            selected_choices.values_list('id', flat=True)
        )

        if correct_ids == selected_ids:
            total_score += question.grade

    context = {
        'course': course,
        'grade': total_score,
        'choices': choices,
    }

    return render(
        request,
        'onlinecourse/exam_result_bootstrap.html',
        context
    )
