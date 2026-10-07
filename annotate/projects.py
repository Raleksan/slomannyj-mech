"""Creates Label Studio projects from gold packets, inside the container.

Run by scripts/annotate.sh local projects PACKET...: a packet is a task
(place) or its repeat set (place-repeat). Each becomes a project of that
name, with annotate/configs/TASK.xml and gold/BOOK/packets/PACKET.json,
owned by the one user there, saved through Label Studio's own import code
(no API token needed). A project whose name exists is left alone.
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
from users.models import User  # noqa: E402

src = sys.argv[1]
users = list(User.objects.all())
if len(users) != 1:
    sys.exit(f"expected one user, found {len(users)}: sign up first, or create projects by hand")
user = users[0]
existing = set(Project.objects.values_list("title", flat=True))
for packet in sys.argv[2:]:
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
