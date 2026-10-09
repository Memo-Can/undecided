from datetime import timedelta

from django.core.paginator import EmptyPage, Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch
from django.http import Http404, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.views import read_json

from .models import Option, Poll, Vote

PAGE_SIZE = 10
MAX_POLLS_PER_HOUR = 10


def error(errors, status=400):
    return JsonResponse({"errors": errors}, status=status)


def valid_voter_key(value):
    return isinstance(value, str) and 0 < len(value) <= 64


def poll_queryset():
    # explicit order_by: Meta.ordering is ignored once the query is grouped by annotate(Count)
    options = Option.objects.annotate(votes_count=Count("votes")).order_by("position", "id")
    return Poll.objects.select_related("author").prefetch_related(Prefetch("options", queryset=options))


def my_votes(request, polls, voter_key):
    """{poll_id: option_id} for the current user or anonymous voter_key, in one query."""
    if request.user.is_authenticated:
        who = {"user": request.user}
    elif valid_voter_key(voter_key):
        who = {"voter_key": voter_key}
    else:
        return {}
    rows = Vote.objects.filter(poll__in=[p.id for p in polls], **who).values_list("poll_id", "option_id")
    return dict(rows)


def poll_payload(poll, voted):
    options = list(poll.options.all())
    return {
        "id": poll.id,
        "question": poll.question,
        "author": poll.author.username,
        "created_at": poll.created_at.isoformat().replace("+00:00", "Z"),
        "total_votes": sum(o.votes_count for o in options),
        "options": [{"id": o.id, "text": o.text, "votes": o.votes_count} for o in options],
        "my_vote": voted.get(poll.id),
    }


def validate_new_poll(data):
    errors = {}
    question = data.get("question")
    question = question.strip() if isinstance(question, str) else ""
    if not question:
        errors["question"] = ["Soru zorunludur."]
    elif len(question) > 200:
        errors["question"] = ["Soru en fazla 200 karakter olabilir."]

    raw = data.get("options")
    options = []
    if not isinstance(raw, list):
        errors["options"] = ["Seçenekler liste olmalı."]
    else:
        options = [o.strip() if isinstance(o, str) else "" for o in raw]
        if not 2 <= len(options) <= 5:
            errors["options"] = ["Bir ankette en az 2, en çok 5 seçenek olmalı."]
        elif any(not o for o in options):
            errors["options"] = ["Seçenekler boş olamaz."]
        elif any(len(o) > 100 for o in options):
            errors["options"] = ["Seçenek en fazla 100 karakter olabilir."]
        elif len({o.casefold() for o in options}) != len(options):
            errors["options"] = ["Seçenekler birbirinden farklı olmalı."]
    return question, options, errors


@require_http_methods(["GET", "POST"])
def poll_list(request):
    if request.method == "POST":
        return create_poll(request)

    try:
        page_number = int(request.GET.get("page", 1))
    except ValueError:
        page_number = 1
    paginator = Paginator(poll_queryset(), PAGE_SIZE)
    try:
        page = paginator.page(max(page_number, 1))
    except EmptyPage:
        return JsonResponse({"results": [], "page": page_number, "has_next": False})
    polls = list(page.object_list)
    voted = my_votes(request, polls, request.headers.get("X-Voter-Key"))
    return JsonResponse({
        "results": [poll_payload(p, voted) for p in polls],
        "page": page.number,
        "has_next": page.has_next(),
    })


def create_poll(request):
    if not request.user.is_authenticated:
        return error({"__all__": ["Anket oluşturmak için giriş yapmalısın."]}, 401)
    recent = Poll.objects.filter(author=request.user, created_at__gte=timezone.now() - timedelta(hours=1)).count()
    if recent >= MAX_POLLS_PER_HOUR:
        return error({"__all__": [f"Saatte en fazla {MAX_POLLS_PER_HOUR} anket açabilirsin. Biraz sonra tekrar dene."]}, 429)
    question, options, errors = validate_new_poll(read_json(request))
    if errors:
        return error(errors)
    with transaction.atomic():
        poll = Poll.objects.create(question=question, author=request.user)
        Option.objects.bulk_create(Option(poll=poll, text=t, position=i) for i, t in enumerate(options))
    return JsonResponse(poll_payload(poll_queryset().get(pk=poll.pk), {}), status=201)


@require_GET
def poll_detail(request, poll_id):
    try:
        poll = poll_queryset().get(pk=poll_id)
    except Poll.DoesNotExist:
        raise Http404
    voted = my_votes(request, [poll], request.headers.get("X-Voter-Key"))
    return JsonResponse(poll_payload(poll, voted))


@require_POST
def vote(request, poll_id):
    data = read_json(request)
    option_id = data.get("option_id")
    voter_key = data.get("voter_key")
    if isinstance(option_id, bool) or not isinstance(option_id, int):
        return error({"option_id": ["Geçerli bir seçenek seç."]})
    if not request.user.is_authenticated and not valid_voter_key(voter_key):
        return error({"voter_key": ["Oy vermek için voter_key gerekli."]})
    try:
        option = Option.objects.get(pk=option_id, poll_id=poll_id)
    except Option.DoesNotExist:
        if not Poll.objects.filter(pk=poll_id).exists():
            raise Http404
        return error({"option_id": ["Bu seçenek bu ankete ait değil."]})

    who = {"user": request.user} if request.user.is_authenticated else {"voter_key": voter_key}
    already = error({"__all__": ["Bu ankete zaten oy verdin."]}, 409)
    if Vote.objects.filter(poll_id=poll_id, **who).exists():
        return already
    try:
        with transaction.atomic():
            Vote.objects.create(option=option, poll_id=poll_id, **who)
    except IntegrityError:
        return already
    poll = poll_queryset().get(pk=poll_id)
    return JsonResponse(poll_payload(poll, {poll.id: option.id}), status=201)
