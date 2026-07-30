from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    """
    Default pagination that lets clients request a larger page.

    Dropdown lookups (classes, sections, teachers) need the full list rather
    than the first page, otherwise options silently go missing.
    """

    page_size_query_param = "page_size"
    max_page_size = 500
