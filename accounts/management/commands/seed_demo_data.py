from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from academics.models import ClassLevel, ClassSubject, PassingCriteria, Section, Subject, TeacherSubjectAssignment
from accounts.models import ParentProfile, RoleChoices, TeacherProfile, UserRole
from admissions.models import Admission, Inquiry, VisitorLog
from exams.models import Exam, Mark
from fees.models import FeeStructure, Invoice, Payment
from schools.models import AcademicYear, School, SchoolSubscription
from students.models import ParentStudentLink, Student

User = get_user_model()
DEFAULT_PASSWORD = "DemoPass123!"


class Command(BaseCommand):
    help = "Seed demo school, users, roles and sample academic data."

    def handle(self, *args, **options):
        school, _ = School.objects.get_or_create(
            slug="demo-school",
            defaults={"name": "Demo School", "address": "Main Road, Lahore"},
        )
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
            ("teacher@demo.school", "Ali", "Teacher", "MSc Mathematics"),
            ("fatima@demo.school", "Fatima", "Noor", "MA English"),
            ("hassan@demo.school", "Hassan", "Raza", "MSc Physics"),
            ("sadia@demo.school", "Sadia", "Iqbal", "B.Ed"),
        ]
        for email, first_name, last_name, qualification in teacher_specs:
            teacher_account = self._upsert_user(email, first_name, last_name, school, RoleChoices.TEACHER)
            profile, _ = TeacherProfile.objects.get_or_create(
                user=teacher_account,
                defaults={"school": school, "qualification": qualification},
            )
            if profile.school_id != school.id:
                profile.school = school
            if profile.qualification != qualification:
                profile.qualification = qualification
            if not profile.employee_id.startswith("TCH-"):
                profile.employee_id = ""
            profile.save()
            teacher_profiles.append(profile)

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
                sections.append(section)

        subjects = []
        for subject_name in ["Mathematics", "English", "Science", "Computer", "Urdu", "Islamiyat"]:
            subject, _ = Subject.objects.get_or_create(school=school, name=subject_name)
            subjects.append(subject)

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
            inquiry, _ = Inquiry.objects.get_or_create(
                school=school,
                full_name=f"Prospect {idx + 1}",
                defaults={
                    "phone": f"0311{idx+1000000}",
                    "interested_class": class_levels[idx % len(class_levels)].name,
                    "source": "website" if idx % 2 == 0 else "walk_in",
                    "status": inquiry_statuses[idx % len(inquiry_statuses)],
                },
            )
            inquiry.status = inquiry_statuses[idx % len(inquiry_statuses)]
            inquiry.phone = f"0311{idx+1000000}"
            inquiry.interested_class = class_levels[idx % len(class_levels)].name
            inquiry.source = "website" if idx % 2 == 0 else "walk_in"
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
            Admission.objects.get_or_create(
                school=school,
                inquiry=inquiry,
                defaults={
                    "student": students[idx] if inquiry.status in ["admitted", "applied"] else None,
                    "decision": "approved" if inquiry.status == "admitted" else "pending",
                },
            )

        exam, _ = Exam.objects.get_or_create(
            school=school,
            academic_year=academic_year,
            name="Midterm",
            defaults={"starts_on": date.today(), "ends_on": date.today()},
        )
        for idx, student in enumerate(students[:20]):
            Mark.objects.get_or_create(
                school=school,
                exam=exam,
                student=student,
                subject=subjects[idx % len(subjects)],
                defaults={
                    "teacher": teacher_profiles[idx % len(teacher_profiles)],
                    "marks_obtained": 60 + (idx % 35),
                    "max_marks": 100,
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

