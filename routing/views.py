import json
from urllib.parse import urlencode

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .errors import PlanError
from .map_html import render_map_html
from .planner import build_plan


def _params(request):
    """Accept GET query params or a JSON POST body: start, finish, [corridor_miles]."""
    if request.method == "POST":
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            raise PlanError("Request body must be valid JSON.", code="invalid_json")
        if not isinstance(body, dict):
            raise PlanError("Request body must be a JSON object.", code="invalid_json")
    else:
        body = request.GET
    start, finish = body.get("start"), body.get("finish")
    if not start or not finish:
        raise PlanError("Both 'start' and 'finish' are required.", code="missing_parameter")
    corridor = body.get("corridor_miles")
    try:
        corridor = float(corridor) if corridor not in (None, "") else None
    except (TypeError, ValueError):
        raise PlanError("corridor_miles must be a number.", code="invalid_parameter")
    return str(start), str(finish), corridor


def _error(exc: PlanError):
    return JsonResponse({"error": {"code": exc.code, "message": exc.message}}, status=exc.status)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def route_plan(request):
    """JSON: route geometry (GeoJSON), optimal fuel stops, and total fuel cost."""
    try:
        start, finish, corridor = _params(request)
        result = build_plan(start, finish, corridor)
    except PlanError as exc:
        return _error(exc)
    query = {"start": start, "finish": finish}
    if corridor is not None:
        query["corridor_miles"] = corridor
    result["map_url"] = request.build_absolute_uri("/api/route/map/?" + urlencode(query))
    return JsonResponse(result, json_dumps_params={"separators": (",", ":")})


@require_http_methods(["GET"])
def route_map(request):
    """HTML page (Leaflet + OpenStreetMap tiles) showing the route and fuel stops."""
    try:
        start, finish, corridor = _params(request)
        result = build_plan(start, finish, corridor)
    except PlanError as exc:
        return _error(exc)
    return HttpResponse(render_map_html(result))
