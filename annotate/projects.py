"""Creates Label Studio projects from gold packets, inside the container.

Run by scripts/annotate.sh local projects PACKET...: a packet is a task
(place) or its repeat set (place-repeat). Each becomes a project of that
name, with annotate/configs/TASK.xml and gold/BOOK/packets/PACKET.json,
owned by the one user there, saved through Label Studio's own import code
(no API token needed). A project whose name exists is left alone.

With --refresh first, it instead updates the tasks of existing projects
from the packets, matched by gid: only display fields (*_html) may change,
so the answers already given stay with their tasks. A project where any
other field differs is left alone.
"""

import json
import os
import sys

sys.path.insert(0, "/label-studio/label_studio")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.label_studio")

import django  # noqa: E402

django.setup()

from django.db import transaction  # noqa: E402
from data_import.serializers import ImportApiSerializer  # noqa: E402
from projects.models import Project  # noqa: E402
from tasks.models import Task  # noqa: E402
from users.models import User  # noqa: E402

refresh = "--refresh" in sys.argv
args = [a for a in sys.argv[1:] if a != "--refresh"]
src = args[0]


def kept(d: dict) -> dict:
    return {k: v for k, v in d.items() if not k.endswith("_html")}


if refresh:
    for packet in args[1:]:
        project = Project.objects.filter(title=packet).first()
        if project is None:
            print(f"{packet}: no such project")
            continue
        new = {t["data"]["gid"]: t["data"] for t in json.load(open(f"{src}/{packet}.json", encoding="utf-8"))}
        tasks = list(Task.objects.filter(project=project))
        bad = [t.id for t in tasks if t.data.get("gid") not in new or kept(t.data) != kept(new[t.data["gid"]])]
        if bad or len(tasks) != len(new):
            print(f"{packet}: left alone, {len(bad)} tasks differ beyond html "
                  f"({len(tasks)} tasks, {len(new)} in the packet)")
            continue
        changed = 0
        with transaction.atomic():
            for t in tasks:
                if t.data != new[t.data["gid"]]:
                    t.data = new[t.data["gid"]]
                    t.save(update_fields=["data"])
                    changed += 1
        print(f"{packet}: {changed} of {len(tasks)} tasks refreshed")
    sys.exit(0)

users = list(User.objects.all())
if len(users) != 1:
    sys.exit(f"expected one user, found {len(users)}: sign up first, or create projects by hand")
user = users[0]
existing = set(Project.objects.values_list("title", flat=True))
for packet in args[1:]:
    if packet in existing:
        print(f"{packet}: already there")
        continue
    task = packet.removesuffix("-repeat")
    config = open(f"{src}/{task}.xml", encoding="utf-8").read()
    data = json.load(open(f"{src}/{packet}.json", encoding="utf-8"))
    with transaction.atomic():
        project = Project.objects.create(title=packet, label_config=config, created_by=user,
                                         organization=user.active_organization)
        ser = ImportApiSerializer(data=data, many=True, context={"project": project, "user": user})
        ser.is_valid(raise_exception=True)
        tasks = ser.save(project_id=project.id)
        project.update_tasks_counters_and_task_states(
            tasks_queryset=tasks, maximum_annotations_changed=False,
            overlap_cohort_percentage_changed=False, tasks_number_changed=True,
            recalculate_stats_counts={"task_count": len(tasks), "annotation_count": 0, "prediction_count": 0})
        project.summary.update_data_columns(data)
    print(f"{packet}: {len(tasks)} tasks")
