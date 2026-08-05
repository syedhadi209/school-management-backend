from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone as dj_timezone

from academics.models import ClassLevel, ClassSubject, PassingCriteria, Section, Subject, TeacherSubjectAssignment
from accounts.models import ParentProfile, RoleChoices, TeacherProfile, UserRole
from admissions.models import Admission, Inquiry, VisitorLog
from attendance.models import AttendanceRecord, AttendanceSession
from exams.models import Exam, Mark, MarkSheet
from fees.models import FeeStructure, Invoice, Payment
from schools.models import AcademicYear, School, SchoolSubscription
from students.models import ParentStudentLink, Student
from timetable.models import TimetableEntry

User = get_user_model()
DEFAULT_PASSWORD = "DemoPass123!"


class Command(BaseCommand):
    help = "Seed demo school, users, roles and sample academic data."

    def handle(self, *args, **options):
        school, _ = School.objects.get_or_create(
            slug="demo-school",
            defaults={"name": "Demo School", "address": "Main Road, Lahore", "timezone": "Asia/Karachi"},
        )
        if not school.timezone:
            school.timezone = "Asia/Karachi"
            school.save(update_fields=["timezone"])
        SchoolSubscription.objects.get_or_create(school=school)

        academic_year, _ = AcademicYear.objects.get_or_create(
            school=school,
            name="2026-2027",
            defaults={
                "start_date": date(2026, 4, 1),
                "end_date": date(2027, 3, 31),
                "is_active": True,
            },
        )

        school_admin = self._upsert_user("admin@demo.school", "School", "Admin", school, RoleChoices.SCHOOL_ADMIN)
        manager = self._upsert_user("manager@demo.school", "Aisha", "Manager", school, RoleChoices.MANAGER)
        teacher_user = self._upsert_user("teacher@demo.school", "Ali", "Teacher", school, RoleChoices.TEACHER)
        parent_user = self._upsert_user("parent@demo.school", "Sara", "Parent", school, RoleChoices.PARENT)
        self._upsert_user("superadmin@platform.local", "Super", "Admin", None, RoleChoices.SUPER_ADMIN, True)

        teacher_profiles = []
        teacher_specs = [
            ("teacher@demo.school", "Ali", "Teacher", "MSc Mathematics", "3520211111111", 85000, "subject_teacher", time(7, 30), time(14, 30), ["Mathematics", "Science"]),
            ("fatima@demo.school", "Fatima", "Noor", "MA English", "3520222222222", 78000, "subject_teacher", time(7, 30), time(14, 30), ["English", "Urdu"]),
            ("hassan@demo.school", "Hassan", "Raza", "MSc Physics", "3520233333333", 82000, "sports_teacher", time(8, 0), time(15, 0), ["Science", "Mathematics"]),
            ("sadia@demo.school", "Sadia", "Iqbal", "B.Ed", "3520244444444", 70000, "principal", time(7, 0), time(15, 0), ["Islamiyat", "Urdu"]),
        ]
        teacher_subject_names: dict[str, list[str]] = {}
        for email, first_name, last_name, qualification, cnic, salary, designation, shift_start, shift_end, subject_names in teacher_specs:
            teacher_account = self._upsert_user(email, first_name, last_name, school, RoleChoices.TEACHER)
            profile, _ = TeacherProfile.objects.get_or_create(
                user=teacher_account,
                defaults={
                    "school": school,
                    "qualification": qualification,
                    "monthly_salary": salary,
                    "designation": designation,
                    "shift_start_time": shift_start,
                    "shift_end_time": shift_end,
                    "cnic": cnic,
                    "phone_number": f"0300{1000000 + len(teacher_profiles)}",
                    "address": f"House {len(teacher_profiles) + 1}, Demo Street, Lahore",
                },
            )
            profile.school = school
            profile.qualification = qualification
            profile.monthly_salary = salary
            profile.designation = designation
            profile.shift_start_time = shift_start
            profile.shift_end_time = shift_end
            profile.cnic = cnic
            profile.phone_number = f"0300{1000000 + len(teacher_profiles)}"
            profile.address = f"House {len(teacher_profiles) + 1}, Demo Street, Lahore"
            if not profile.employee_id.startswith("TCH-"):
                profile.employee_id = ""
            profile.save()
            teacher_profiles.append(profile)
            teacher_subject_names[email] = subject_names

        parent_profiles = []
        parent_specs = [
            ("parent@demo.school", "Sara", "Parent"),
            ("nida.parent@demo.school", "Nida", "Rahman"),
            ("omar.parent@demo.school", "Omar", "Khalid"),
        ]
        for email, first_name, last_name in parent_specs:
            parent_account = self._upsert_user(email, first_name, last_name, school, RoleChoices.PARENT)
            profile, _ = ParentProfile.objects.get_or_create(user=parent_account, defaults={"school": school})
            if profile.school_id != school.id:
                profile.school = school
                profile.save(update_fields=["school"])
            parent_profiles.append(profile)

        class_level_names = ["Class 1", "Class 2", "Class 3", "Class 4", "Class 5", "Class 6", "Class 7", "Class 8"]
        class_levels = []
        for position, level_name in enumerate(class_level_names, start=1):
            # Prefer "Class N" naming; migrate any leftover "Grade N" rows from older seeds.
            ClassLevel.objects.filter(
                school=school,
                academic_year=academic_year,
                name=f"Grade {position}",
            ).update(name=level_name)
            level, _ = ClassLevel.objects.get_or_create(
                school=school,
                academic_year=academic_year,
                name=level_name,
                defaults={"order": position},
            )
            if level.order != position:
                level.order = position
                level.save(update_fields=["order"])
            class_levels.append(level)

        shifts = ["mwf", "tthf", "daily"]
        sections = []
        for idx, level in enumerate(class_levels):
            for section_name in ["A", "B"]:
                teacher_profile = teacher_profiles[(idx + (0 if section_name == "A" else 1)) % len(teacher_profiles)]
                section, _ = Section.objects.get_or_create(
                    school=school,
                    class_level=level,
                    name=section_name,
                    defaults={
                        "class_teacher": teacher_profile,
                        "capacity": 30 + (idx % 3) * 5,
                        "shift": shifts[idx % len(shifts)],
                    },
                )
                section.class_teacher = teacher_profile
                section.capacity = 30 + (idx % 3) * 5
                section.shift = shifts[idx % len(shifts)]
                section.save(update_fields=["class_teacher", "capacity", "shift"])
                second_teacher = teacher_profiles[(idx + 2) % len(teacher_profiles)]
                section.teachers.set({teacher_profile, second_teacher})
                sections.append(section)

        subjects = []
        subject_by_name: dict[str, Subject] = {}
        for subject_name in ["Mathematics", "English", "Science", "Computer", "Urdu", "Islamiyat"]:
            subject, _ = Subject.objects.get_or_create(school=school, name=subject_name)
            subjects.append(subject)
            subject_by_name[subject_name] = subject

        for profile in teacher_profiles:
            names = teacher_subject_names.get(profile.user.email, [])
            profile.subjects_taught.set([subject_by_name[name] for name in names if name in subject_by_name])

        for level in class_levels:
            for subject in subjects:
                ClassSubject.objects.get_or_create(school=school, class_level=level, subject=subject)
            PassingCriteria.objects.get_or_create(
                school=school,
                class_level=level,
                academic_year=academic_year,
                defaults={"min_percentage": Decimal("50.00")},
            )

        for section_idx, section in enumerate(sections):
            for subject_idx, subject in enumerate(subjects[:4]):
                teacher_profile = teacher_profiles[(section_idx + subject_idx) % len(teacher_profiles)]
                TeacherSubjectAssignment.objects.get_or_create(
                    school=school,
                    teacher=teacher_profile,
                    subject=subject,
                    section=section,
                    academic_year=academic_year,
                )

        # Rebuild weekly timetable without teacher double-booking.
        # Older seeds fell back to a busy teacher when no free section teacher existed,
        # which produced impossible overlapping lectures (visible in the teacher portal).
        # Clear attendance first: TimetableEntry delete SET_NULLs session.timetable_entry,
        # and multiple orphans with the same slot identity violate att_sess_unique_orphan_slot.
        AttendanceRecord.objects.filter(school=school, session__academic_year=academic_year).delete()
        AttendanceSession.objects.filter(school=school, academic_year=academic_year).delete()
        TimetableEntry.objects.filter(school=school, academic_year=academic_year).delete()

        lecture_blocks = [
            (0, time(7, 30), time(8, 20)),
            (1, time(8, 20), time(9, 10)),
            (2, time(9, 30), time(10, 20)),
            (3, time(10, 20), time(11, 10)),
            (4, time(11, 30), time(12, 20)),
        ]

        def teacher_is_free(teacher_profile, day_of_week, start, end) -> bool:
            return not TimetableEntry.objects.filter(
                school=school,
                academic_year=academic_year,
                teacher=teacher_profile,
                day_of_week=day_of_week,
                start_time__lt=end,
                end_time__gt=start,
                is_active=True,
            ).exists()

        # Round-robin cursor so sections share limited teachers fairly across the week.
        section_cursor = 0
        for day in range(5):  # Mon–Fri
            for section in sections:
                TimetableEntry.objects.create(
                    school=school,
                    academic_year=academic_year,
                    section=section,
                    day_of_week=day,
                    start_time=time(9, 10),
                    end_time=time(9, 30),
                    slot_type=TimetableEntry.SLOT_BREAK,
                    label="Recess",
                    subject=None,
                    teacher=None,
                    is_active=True,
                )
                TimetableEntry.objects.create(
                    school=school,
                    academic_year=academic_year,
                    section=section,
                    day_of_week=day,
                    start_time=time(11, 10),
                    end_time=time(11, 30),
                    slot_type=TimetableEntry.SLOT_BREAK,
                    label="Lunch",
                    subject=None,
                    teacher=None,
                    is_active=True,
                )

            for block_idx, (subject_offset, start, end) in enumerate(lecture_blocks):
                # At most one lecture per teacher in this time window.
                assigned_teachers: set[int] = set()
                checked = 0
                while len(assigned_teachers) < len(teacher_profiles) and checked < len(sections):
                    section = sections[section_cursor % len(sections)]
                    section_idx = section_cursor % len(sections)
                    section_cursor += 1
                    checked += 1

                    section_teachers = list(section.teachers.all())
                    teacher_profile = next(
                        (
                            candidate
                            for candidate in section_teachers
                            if candidate.id not in assigned_teachers
                            and teacher_is_free(candidate, day, start, end)
                        ),
                        None,
                    )
                    if teacher_profile is None:
                        # No free teacher already on this section — skip rather than double-book
                        # or silently attach a random teacher to the section roster.
                        continue

                    subject = subjects[(section_idx + subject_offset + block_idx) % len(subjects)]
                    TimetableEntry.objects.create(
                        school=school,
                        academic_year=academic_year,
                        section=section,
                        day_of_week=day,
                        start_time=start,
                        end_time=end,
                        slot_type=TimetableEntry.SLOT_LECTURE,
                        subject=subject,
                        teacher=teacher_profile,
                        label="",
                        is_active=True,
                    )
                    assigned_teachers.add(teacher_profile.id)

        first_names = [
            "Hamza", "Ayesha", "Bilal", "Sana", "Usman", "Mariam", "Farhan", "Hira", "Saad", "Noor",
            "Zain", "Iqra", "Anas", "Laiba", "Talha", "Mahnoor", "Rayyan", "Mehwish", "Daniyal", "Komal",
            "Arham", "Areeba", "Junaid", "Zoya", "Ammar", "Hafsa", "Shayan", "Eman", "Musa", "Aiman",
            "Hashir", "Aleena", "Taimoor", "Rida", "Basit", "Hadia", "Moin", "Anaya", "Yasir", "Nimra",
        ]
        last_names = [
            "Khan", "Ahmed", "Ali", "Raza", "Iqbal", "Hassan", "Nawaz", "Qureshi", "Malik", "Javed",
            "Siddiqui", "Farooq", "Shaikh", "Akram", "Shah", "Mehmood", "Amin", "Chaudhry", "Hussain", "Aslam",
        ]
        statuses = ["active", "pending", "waiting_list", "withdrawn", "archived", "repeating"]
        regions = ["Lahore", "Karachi", "Islamabad", "Peshawar", "Quetta", "Multan", "Faisalabad"]
        students = []
        for idx in range(40):
            first_name = first_names[idx]
            last_name = last_names[idx % len(last_names)]
            section = sections[idx % len(sections)]
            status = statuses[idx % len(statuses)]
            student, _ = Student.objects.get_or_create(
                school=school,
                first_name=first_name,
                last_name=last_name,
                defaults={
                    "section": section,
                    "status": status,
                    "region": regions[idx % len(regions)],
                    "guardian_phone": f"0300{idx+1000000}",
                    "parent_email": parent_profiles[idx % len(parent_profiles)].user.email,
                    "father_name": f"Father of {first_name}",
                    "mother_name": f"Mother of {first_name}",
                    "father_cnic": f"35202{10000000 + idx:08d}",
                    "address": f"House {idx + 1}, Demo Street, {regions[idx % len(regions)]}",
                    "parent_occupation": ["Business", "Teacher", "Engineer", "Doctor"][idx % 4],
                    "gender": "male" if idx % 2 == 0 else "female",
                    "admission_date": date.today() - timedelta(days=30 + idx),
                },
            )
            student.section = section
            student.status = status
            # Force readable auto IDs for older seed formats.
            if not student.roll_number.startswith("STU-"):
                student.roll_number = ""
            student.region = regions[idx % len(regions)]
            student.guardian_phone = f"0300{idx+1000000}"
            student.parent_email = parent_profiles[idx % len(parent_profiles)].user.email
            student.father_name = f"Father of {first_name}"
            student.mother_name = f"Mother of {first_name}"
            student.father_cnic = f"35202{10000000 + idx:08d}"
            student.address = f"House {idx + 1}, Demo Street, {regions[idx % len(regions)]}"
            student.parent_occupation = ["Business", "Teacher", "Engineer", "Doctor"][idx % 4]
            student.gender = "male" if idx % 2 == 0 else "female"
            student.admission_date = date.today() - timedelta(days=30 + idx)
            student.save()
            students.append(student)

        for idx, student in enumerate(students):
            parent = parent_profiles[idx % len(parent_profiles)]
            ParentStudentLink.objects.get_or_create(
                school=school,
                parent=parent,
                student=student,
                defaults={"relation": "Mother" if idx % 2 == 0 else "Father"},
            )

        # Seed a couple of submitted attendance sessions for Ali's Monday lectures.
        ali_teacher = next((profile for profile in teacher_profiles if profile.user.email == "teacher@demo.school"), None)
        if ali_teacher is not None:
            monday = date.today() - timedelta(days=date.today().weekday())
            ali_lectures = list(
                TimetableEntry.objects.filter(
                    school=school,
                    teacher=ali_teacher,
                    slot_type=TimetableEntry.SLOT_LECTURE,
                    day_of_week=0,
                    is_active=True,
                ).select_related("section", "subject", "academic_year")[:2]
            )
            statuses_cycle = [
                AttendanceRecord.STATUS_PRESENT,
                AttendanceRecord.STATUS_ABSENT,
                AttendanceRecord.STATUS_LATE,
                AttendanceRecord.STATUS_LEAVE,
            ]
            for lecture in ali_lectures:
                session, _ = AttendanceSession.objects.update_or_create(
                    timetable_entry=lecture,
                    date=monday,
                    defaults={
                        "school": school,
                        "academic_year": lecture.academic_year,
                        "section": lecture.section,
                        "teacher": lecture.teacher,
                        "subject": lecture.subject,
                        "day_of_week": lecture.day_of_week,
                        "start_time": lecture.start_time,
                        "end_time": lecture.end_time,
                        "status": AttendanceSession.STATUS_SUBMITTED,
                        "taken_by": ali_teacher.user,
                        "taken_at": dj_timezone.now(),
                        "notes": "Seeded demo attendance",
                    },
                )
                section_students = list(
                    Student.objects.filter(school=school, section=lecture.section, status="active").order_by("id")
                )
                for student_idx, student in enumerate(section_students):
                    AttendanceRecord.objects.update_or_create(
                        session=session,
                        student=student,
                        defaults={
                            "school": school,
                            "status": statuses_cycle[student_idx % len(statuses_cycle)],
                            "remarks": "Seeded" if student_idx % 4 == 1 else "",
                        },
                    )

        fee_structures = []
        for level in class_levels:
            fee_structure, _ = FeeStructure.objects.get_or_create(
                school=school,
                class_level=level,
                name=f"{level.name} Monthly Tuition",
                defaults={"amount": 10000 + (class_levels.index(level) * 1200)},
            )
            fee_structures.append(fee_structure)

        for idx, student in enumerate(students):
            fee_structure = fee_structures[idx % len(fee_structures)]
            total_amount = fee_structure.amount
            status = ["unpaid", "partial", "paid"][idx % 3]
            paid_amount = Decimal("0")
            if status == "partial":
                paid_amount = total_amount * Decimal("0.50")
            elif status == "paid":
                paid_amount = total_amount

            invoice, _ = Invoice.objects.get_or_create(
                school=school,
                student=student,
                fee_structure=fee_structure,
                defaults={
                    "total_amount": total_amount,
                    "paid_amount": paid_amount,
                    "status": status,
                    "due_date": date.today() + timedelta(days=(idx % 25) + 5),
                },
            )
            invoice.total_amount = total_amount
            invoice.paid_amount = paid_amount
            invoice.status = status
            invoice.due_date = date.today() + timedelta(days=(idx % 25) + 5)
            invoice.save()

            if paid_amount > 0:
                Payment.objects.get_or_create(
                    school=school,
                    invoice=invoice,
                    amount=paid_amount,
                    defaults={"method": "cash" if idx % 2 == 0 else "bank_transfer"},
                )

        inquiry_statuses = ["new", "contacted", "visited", "applied", "admitted", "rejected"]
        inquiries = []
        for idx in range(18):
            status = inquiry_statuses[idx % len(inquiry_statuses)]
            class_level = class_levels[idx % len(class_levels)]
            defaults = {
                "phone": f"0311{idx+1000000}",
                "interested_class": class_level.name,
                "interested_class_level": class_level,
                "preferred_section": sections[idx % len(sections)] if status in ["applied", "admitted"] else None,
                "source": "website" if idx % 2 == 0 else "walk_in",
                "status": status,
                "first_name": f"Prospect",
                "last_name": f"{idx + 1}",
                "gender": "male" if idx % 2 == 0 else "female",
                "date_of_birth": date(2014, 1, 1) + timedelta(days=idx * 40),
                "father_name": f"Father Prospect {idx + 1}",
                "mother_name": f"Mother Prospect {idx + 1}",
                "father_cnic": f"35203{10000000 + idx:08d}",
                "address": f"Prospect House {idx + 1}, Demo Town",
                "region": regions[idx % len(regions)],
                "parent_email": f"prospect.parent{idx + 1}@demo.school",
                "parent_phone": f"0311{idx+1000000}",
                "notes": "Seeded inquiry",
            }
            if status == "applied":
                defaults["application_date"] = date.today() - timedelta(days=idx)
            if status == "rejected":
                defaults["rejection_reason"] = "Did not meet age criteria"
            inquiry, _ = Inquiry.objects.get_or_create(
                school=school,
                full_name=f"Prospect {idx + 1}",
                defaults=defaults,
            )
            for key, value in defaults.items():
                setattr(inquiry, key, value)
            inquiry.status = status
            inquiry.save()
            inquiries.append(inquiry)

        for idx in range(12):
            VisitorLog.objects.get_or_create(
                school=school,
                visitor_name=f"Visitor {idx + 1}",
                purpose="Admission Inquiry",
                defaults={"met_with": "Front Desk"},
            )

        for idx, inquiry in enumerate(inquiries[:10]):
            decision = "approved" if inquiry.status == "admitted" else "pending"
            linked_student = None
            if inquiry.status == "admitted":
                linked_student = students[idx]
            admission, _ = Admission.objects.get_or_create(
                school=school,
                inquiry=inquiry,
                defaults={
                    "student": linked_student,
                    "decision": decision,
                },
            )
            if admission.decision != decision:
                admission.decision = decision
            # Avoid colliding OneToOne student links across re-seeds.
            if linked_student and (
                admission.student_id is None
                or not Admission.objects.filter(student=linked_student).exclude(pk=admission.pk).exists()
            ):
                admission.student = linked_student
            admission.save()

        # Exams: one published class test + one open midterm with sample sheets.
        ali_assignment = None
        if ali_teacher is not None:
            ali_assignment = (
                TeacherSubjectAssignment.objects.filter(
                    teacher=ali_teacher, school=school, academic_year=academic_year
                )
                .select_related("section", "subject")
                .first()
            )

        if ali_assignment is not None:
            class_test, _ = Exam.objects.get_or_create(
                academic_year=academic_year,
                section=ali_assignment.section,
                subject=ali_assignment.subject,
                name="Chapter Quiz 1",
                defaults={
                    "school": school,
                    "exam_type": Exam.TYPE_CLASS_TEST,
                    "status": Exam.STATUS_PUBLISHED,
                    "max_marks": Decimal("50"),
                    "starts_on": date.today() - timedelta(days=7),
                    "ends_on": date.today() - timedelta(days=7),
                    "created_by": ali_teacher.user,
                    "published_at": dj_timezone.now(),
                    "published_by": ali_teacher.user,
                },
            )
            if class_test.exam_type != Exam.TYPE_CLASS_TEST:
                class_test.exam_type = Exam.TYPE_CLASS_TEST
                class_test.status = Exam.STATUS_PUBLISHED
                class_test.max_marks = Decimal("50")
                class_test.published_at = class_test.published_at or dj_timezone.now()
                class_test.published_by = class_test.published_by or ali_teacher.user
                class_test.save()

            sheet, _ = MarkSheet.objects.get_or_create(
                exam=class_test,
                section=ali_assignment.section,
                subject=ali_assignment.subject,
                defaults={
                    "school": school,
                    "academic_year": academic_year,
                    "teacher": ali_teacher,
                    "status": MarkSheet.STATUS_SUBMITTED,
                    "max_marks": Decimal("50"),
                    "submitted_at": dj_timezone.now(),
                    "submitted_by": ali_teacher.user,
                    "notes": "Seeded class test",
                },
            )
            if sheet.status != MarkSheet.STATUS_SUBMITTED:
                sheet.status = MarkSheet.STATUS_SUBMITTED
                sheet.submitted_at = sheet.submitted_at or dj_timezone.now()
                sheet.submitted_by = sheet.submitted_by or ali_teacher.user
                sheet.save()

            section_students = list(
                Student.objects.filter(
                    school=school, section=ali_assignment.section, status="active"
                ).order_by("id")
            )
            for idx, student in enumerate(section_students):
                Mark.objects.update_or_create(
                    exam=class_test,
                    student=student,
                    subject=ali_assignment.subject,
                    defaults={
                        "school": school,
                        "sheet": sheet,
                        "teacher": ali_teacher,
                        "marks_obtained": Decimal(30 + (idx % 20)),
                        "max_marks": Decimal("50"),
                        "remarks": "",
                    },
                )

        midterm, _ = Exam.objects.get_or_create(
            school=school,
            academic_year=academic_year,
            name="Midterm",
            defaults={
                "exam_type": Exam.TYPE_MIDTERM,
                "status": Exam.STATUS_OPEN,
                "max_marks": Decimal("100"),
                "starts_on": date.today(),
                "ends_on": date.today() + timedelta(days=7),
                "created_by": school_admin,
            },
        )
        if midterm.exam_type != Exam.TYPE_MIDTERM:
            midterm.exam_type = Exam.TYPE_MIDTERM
            midterm.status = Exam.STATUS_OPEN
            midterm.section = None
            midterm.subject = None
            midterm.max_marks = Decimal("100")
            midterm.save()

        # Seed one midterm sheet for Ali's assignment (submitted, unpublished exam).
        if ali_assignment is not None:
            mid_sheet, _ = MarkSheet.objects.get_or_create(
                exam=midterm,
                section=ali_assignment.section,
                subject=ali_assignment.subject,
                defaults={
                    "school": school,
                    "academic_year": academic_year,
                    "teacher": ali_teacher,
                    "status": MarkSheet.STATUS_SUBMITTED,
                    "max_marks": Decimal("100"),
                    "submitted_at": dj_timezone.now(),
                    "submitted_by": ali_teacher.user,
                    "notes": "Seeded midterm sheet",
                },
            )
            mid_students = list(
                Student.objects.filter(
                    school=school, section=ali_assignment.section, status="active"
                ).order_by("id")
            )
            for idx, student in enumerate(mid_students):
                Mark.objects.update_or_create(
                    exam=midterm,
                    student=student,
                    subject=ali_assignment.subject,
                    defaults={
                        "school": school,
                        "sheet": mid_sheet,
                        "teacher": ali_teacher,
                        "marks_obtained": Decimal(60 + (idx % 35)),
                        "max_marks": Decimal("100"),
                        "remarks": "",
                    },
                )

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully."))
        self.stdout.write("Login credentials:")
        self.stdout.write(f"School Admin: admin@demo.school / {DEFAULT_PASSWORD}")
        self.stdout.write(f"Manager: manager@demo.school / {DEFAULT_PASSWORD}")
        self.stdout.write(f"Teacher: teacher@demo.school / {DEFAULT_PASSWORD}")
        self.stdout.write(f"Parent: parent@demo.school / {DEFAULT_PASSWORD}")
        self.stdout.write(f"Super Admin: superadmin@platform.local / {DEFAULT_PASSWORD}")

    def _upsert_user(self, email, first_name, last_name, school, role, is_superuser=False):
        defaults = {
            "first_name": first_name,
            "last_name": last_name,
            "active_school": school,
            "is_staff": is_superuser,
            "is_superuser": is_superuser,
            "username": email,
        }
        user, created = User.objects.get_or_create(email=email, defaults=defaults)
        if created:
            user.set_password(DEFAULT_PASSWORD)
            user.save()
        else:
            changed = False
            if not user.username:
                user.username = email
                changed = True
            if school and user.active_school_id != school.id:
                user.active_school = school
                changed = True
            if is_superuser and not user.is_superuser:
                user.is_superuser = True
                user.is_staff = True
                changed = True
            if changed:
                user.save()
            if not user.check_password(DEFAULT_PASSWORD):
                user.set_password(DEFAULT_PASSWORD)
                user.save()

        if school:
            UserRole.objects.get_or_create(user=user, school=school, role=role)
        return user

