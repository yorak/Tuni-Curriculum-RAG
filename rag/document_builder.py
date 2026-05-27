from llama_index.core import Document


def safe_get_name(value):
    if isinstance(value, dict):
        return value.get("en") or value.get("fi") or str(value)
    return str(value)


def safe_get_text(value):
    if isinstance(value, dict):
        return value.get("en") or value.get("fi") or ""
    if value is None:
        return ""
    return str(value)


def build_documents(data):
    documents = []

    # -----------------------------
    # COURSES
    # -----------------------------
    for c in data.get("courses", []):

        course_name = safe_get_name(c.get("name"))
        description = safe_get_text(c.get("description"))
        learning_outcomes = safe_get_text(c.get("learningOutcomes"))

        credits = c.get("credits", {})
        if isinstance(credits, dict):
            credits_text = f"{credits.get('min', '')}-{credits.get('max', '')}"
        else:
            credits_text = str(credits)

        organisations = c.get("organisations", [])
        responsibility_infos = c.get("responsibilityInfos", [])
        keywords = c.get("keywords", [])
        topic_tags = c.get("topicTags", [])
        module_codes = c.get("moduleCodes", [])
        degree_programmes = c.get("degreeProgrammes", [])

        student_estimate = c.get("annualStudentCountEstimate") or "unknown"

        text = f"""
ENTITY TYPE: COURSE
Course Code: {c.get('code', '')}
Course Name: {course_name}
Language: {c.get('lang', '')}
Credits: {credits_text}
Estimated Annual Students: {student_estimate}

Description:
{description}

Learning Outcomes:
{learning_outcomes}

Keywords:
{", ".join(keywords)}

Topic Tags:
{", ".join(topic_tags)}

Module Codes:
{", ".join(module_codes)}

Degree Programmes:
{", ".join(degree_programmes)}

Organisations:
{", ".join(organisations)}

Responsible Staff IDs:
{", ".join(responsibility_infos)}
""".strip()

        documents.append(
            Document(
                text=text,
                metadata={
                    "entity_type": "course",
                    "id": c.get("id", ""),
                    "code": c.get("code", ""),
                    "name": course_name,
                    "modules": module_codes,
                    "topics": topic_tags,
                    "students": student_estimate,
                },
            )
        )

    # -----------------------------
    # MODULES
    # -----------------------------
    for m in data.get("modules", []):

        module_name = safe_get_name(m.get("name"))
        description = safe_get_text(m.get("description"))

        course_codes = m.get("courseCodes", [])
        topic_tags = m.get("topicTags", [])
        degree_programmes = m.get("degreeProgrammes", [])

        student_volume = m.get("annualStudentVolumeEstimate") or "unknown"

        text = f"""
ENTITY TYPE: MODULE
Module Code: {m.get('code', '')}
Module Name: {module_name}

Estimated Annual Students:
{student_volume}

Description:
{description}

Topic Tags:
{", ".join(topic_tags)}

Course Codes:
{", ".join(course_codes)}

Degree Programmes:
{", ".join(degree_programmes)}
""".strip()

        documents.append(
            Document(
                text=text,
                metadata={
                    "entity_type": "module",
                    "id": m.get("id", ""),
                    "code": m.get("code", ""),
                    "name": module_name,
                    "topics": topic_tags,
                    "students": student_volume,
                },
            )
        )

    # -----------------------------
    # STAFF
    # -----------------------------
    for s in data.get("staff", []):

        research_areas = s.get("researchAreas", [])
        keywords = s.get("keywords", [])
        related_module_codes = s.get("relatedModuleCodes", [])
        related_course_codes = s.get("relatedCourseCodes", [])

        text = f"""
ENTITY TYPE: STAFF
Name: {s.get('name', '')}
Title: {s.get('title', '')}
Email: {s.get('email', '')}

Research Areas:
{", ".join(research_areas)}

Keywords:
{", ".join(keywords)}

Related Module Codes:
{", ".join(related_module_codes)}

Related Course Codes:
{", ".join(related_course_codes)}
""".strip()

        documents.append(
            Document(
                text=text,
                metadata={
                    "entity_type": "staff",
                    "id": s.get("id", ""),
                    "name": s.get("name", ""),
                    "title": s.get("title", ""),
                    "researchAreas": research_areas,
                },
            )
        )

    return documents
