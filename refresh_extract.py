####
# This script contains functions that demonstrate how to add or
# update a given permission for a user on all workbooks. If the particular
# permission is already defined with another mode, it will delete
# the old mode and add the permission with the new mode.
# If the particular permission is not already set, it will add
# the permission with the given mode.
#
# To run the script, you must have installed Python 2.7.9 or later,
# plus the 'requests' library:
#   http://docs.python-requests.org/en/latest/
#
# The script takes in the server address and username as arguments,
# where the server address has no trailing slash (e.g. http://localhost).
# Run the script in terminal by entering:
#   python publish_sample.py <server_address> <username>
#
# When running the script, it will prompt for the following:
# 'Username to update permission for': Enter username to update permissions for
# 'Permission to update':              Enter name of permission to update
# 'Mode to set permission':            Enter either 'Allow' or 'Deny' to set the permission mode
# 'Password':                          Enter password for the user to log in as.
#
# Possible permission names:
#    Read, Write, Filter, AddComment, ViewComments, ShareView, ExportData, ViewUnderlyingData,
#    ExportImage, Delete, ChangeHierarchy, ChangePermissions, WebAuthoring, ExportXml
#
# Possible permission modes:
#    Allow, Deny
####

from version import VERSION
import requests # Contains methods used to make HTTP requests
import xml.etree.ElementTree as ET # Contains methods used to build and parse XML
import sys
import getpass
import math

# The namespace for the REST API is 'http://tableausoftware.com/api' for Tableau Server 9.0
# or 'http://tableau.com/api' for Tableau Server 9.1 or later
xmlns = {'t': 'http://tableau.com/api'}

# All possible permission names
permissions = {"Read", "Write", "Filter", "AddComment", "ViewComments", "ShareView", "ExportData", "ViewUnderlyingData",
               "ExportImage", "Delete", "ChangeHierarchy", "ChangePermissions", "WebAuthoring", "ExportXml"}

# Possible modes for to set the permissions
modes = {"Allow", "Deny"}

# If using python version 3.x, 'raw_input()' is changed to 'input()'
if sys.version[0] == '3': raw_input=input


class ApiCallError(Exception):
    pass


class UserDefinedFieldError(Exception):
    pass


def _encode_for_display(text):
    """
    Encodes strings so they can display as ASCII in a Windows terminal window.
    This function also encodes strings for processing by xml.etree.ElementTree functions.

    Returns an ASCII-encoded version of the text.
    Unicode characters are converted to ASCII placeholders (for example, "?").
    """
    return text.encode('ascii', errors="backslashreplace").decode('utf-8')


def _check_status(server_response, success_code):
    """
    Checks the server response for possible errors.

    'server_response'       the response received from the server
    'success_code'          the expected success code for the response
    Throws an ApiCallError exception if the API call fails.
    """
    if server_response.status_code != success_code:
        parsed_response = ET.fromstring(server_response.text)

        # Obtain the 3 xml tags from the response: error, summary, and detail tags
        error_element = parsed_response.find('t:error', namespaces=xmlns)
        summary_element = parsed_response.find('.//t:summary', namespaces=xmlns)
        detail_element = parsed_response.find('.//t:detail', namespaces=xmlns)

        # Retrieve the error code, summary, and detail if the response contains them
        code = error_element.get('code', 'unknown') if error_element is not None else 'unknown code'
        summary = summary_element.text if summary_element is not None else 'unknown summary'
        detail = detail_element.text if detail_element is not None else 'unknown detail'
        error_message = '{0}: {1} - {2}'.format(code, summary, detail)
        raise ApiCallError(error_message)
    return


def sign_in(server, username, password, site=""):
    """
    Signs in to the server specified with the given credentials

    'server'   specified server address
    'username' is the name (not ID) of the user to sign in as.
               Note that most of the functions in this example require that the user
               have server administrator permissions.
    'password' is the password for the user.
    'site'     is the ID (as a string) of the site on the server to sign in to. The
               default is "", which signs in to the default site.
    Returns the authentication token and the site ID.
    """
    url = server + "/api/{0}/auth/signin".format(VERSION)

    # Builds the request
    xml_request = ET.Element('tsRequest')
    credentials_element = ET.SubElement(xml_request, 'credentials', name=username, password=password)
    ET.SubElement(credentials_element, 'site', contentUrl=site)
    xml_request = ET.tostring(xml_request)

    # Make the request to server
    server_response = requests.post(url, data=xml_request)
    _check_status(server_response, 200)

    # ASCII encode server response to enable displaying to console
    server_response = _encode_for_display(server_response.text)

    # Reads and parses the response
    parsed_response = ET.fromstring(server_response)

    # Gets the auth token and site ID
    token = parsed_response.find('t:credentials', namespaces=xmlns).get('token')
    site_id = parsed_response.find('.//t:site', namespaces=xmlns).get('id')
    user_id = parsed_response.find('.//t:user', namespaces=xmlns).get('id')
    return token, site_id, user_id


def sign_out(server, auth_token):
    """
    Destroys the active session and invalidates authentication token.

    'server'        specified server address
    'auth_token'    authentication token that grants user access to API calls
    """
    url = server + "/api/{0}/auth/signout".format(VERSION)
    server_response = requests.post(url, headers={'x-tableau-auth': auth_token})
    _check_status(server_response, 204)
    return

def get_workbook_id(server, auth_token, user_id, site_id, project_id, workbook_name):
    """
    Gets the id of the desired workbook to relocate.
    'server'        specified server address
    'auth_token'    authentication token that grants user access to API calls
    'user_id'       ID of user with access to workbook
    'site_id'       ID of the site that the user is signed into
    'workbook_name' name of workbook to get ID of
    Returns the workbook id and the project id that contains the workbook.
    """
    url = server + "/api/{0}/sites/{1}/users/{2}/workbooks".format(VERSION, site_id, user_id)
    server_response = requests.get(url, headers={'x-tableau-auth': auth_token})
    _check_status(server_response, 200)
    xml_response = ET.fromstring(_encode_for_display(server_response.text))

    workbooks = xml_response.findall('.//t:workbook', namespaces=xmlns)
    for workbook in workbooks:
        if workbook.get('name') == workbook_name:
            source_project_id = workbook.find('.//t:project', namespaces=xmlns).get('id')
            if source_project_id == project_id:
                return workbook.get('id')
    error = "Workbook named '{0}' not found.".format(workbook_name)
    raise LookupError(error)

def get_datasource_id(server, auth_token, site_id, project_id, datasource_name):
    """
    Gets the id of the desired workbook to relocate.
    'server'        specified server address
    'auth_token'    authentication token that grants user access to API calls
    'user_id'       ID of user with access to workbook
    'site_id'       ID of the site that the user is signed into
    'workbook_name' name of workbook to get ID of
    Returns the workbook id and the project id that contains the workbook.
    """
    url = server + "/api/{0}/sites/{1}/datasources".format(VERSION, site_id)
    server_response = requests.get(url, headers={'x-tableau-auth': auth_token})
    _check_status(server_response, 200)
    xml_response = ET.fromstring(_encode_for_display(server_response.text))

    datasources = xml_response.findall('.//t:datasource', namespaces=xmlns)
    for datasource in datasources:
        if datasource.get('name') == datasource_name:
            source_project_id = datasource.find('.//t:project', namespaces=xmlns).get('id')
            if source_project_id == project_id:
                return datasource.get('id')
    error = "Datasource named '{0}' not found.".format(datasource_name)
    raise LookupError(error)

def get_project_id(server, auth_token, site_id, dest_project):
    """
    Returns the project ID of the desired project
    'server'        specified server address
    'auth_token'    authentication token that grants user access to API calls
    'site_id'       ID of the site that the user is signed into
    'dest_project'  name of destination project to get ID of
    """
    page_num, page_size = 1, 100   # Default paginating values

    # Builds the request
    url = server + "/api/{0}/sites/{1}/projects".format(VERSION, site_id)
    paged_url = url + "?pageSize={0}&pageNumber={1}".format(page_size, page_num)
    server_response = requests.get(paged_url, headers={'x-tableau-auth': auth_token})
    _check_status(server_response, 200)
    xml_response = ET.fromstring(_encode_for_display(server_response.text))

    # Used to determine if more requests are required to find all projects on server
    total_projects = int(xml_response.find('t:pagination', namespaces=xmlns).get('totalAvailable'))
    max_page = int(math.ceil(total_projects / page_size))

    projects = xml_response.findall('.//t:project', namespaces=xmlns)

    # Continue querying if more projects exist on the server
    for page in range(2, max_page + 1):
        paged_url = url + "?pageSize={0}&pageNumber={1}".format(page_size, page)
        server_response = requests.get(paged_url, headers={'x-tableau-auth': auth_token})
        _check_status(server_response, 200)
        xml_response = ET.fromstring(_encode_for_display(server_response.text))
        projects.extend(xml_response.findall('.//t:project', namespaces=xmlns))

    # Look through all projects to find the 'default' one
    for project in projects:
        if project.get('name') == dest_project:
            return project.get('id')
    error = "Project named '{0}' was not found on server".format(dest_project)
    raise LookupError(error)

def get_schedule_id(server, auth_token, schedule_name):
    """
    Gets the id of the desired workbook to relocate.
    'server'        specified server address
    'auth_token'    authentication token that grants user access to API calls
    'user_id'       ID of user with access to workbook
    'site_id'       ID of the site that the user is signed into
    'schedule_name' name of schedule to get ID of
    Returns the workbook id and the project id that contains the workbook.
    """
    url = server + "/api/{0}/schedules".format(VERSION)
    server_response = requests.get(url, headers={'x-tableau-auth': auth_token})
    _check_status(server_response, 200)
    xml_response = ET.fromstring(_encode_for_display(server_response.text))

    schedules = xml_response.findall('.//t:schedule', namespaces=xmlns)
    for schedule in schedules:
        if schedule.get('name') == schedule_name:
            return schedule.get('id')
    error = "Schedule named '{0}' not found.".format(schedule_name)
    raise LookupError(error)

def get_extract_refresh_id(server, auth_token, site_id, schedule_id, object_type, object_id):
    """
    Gets the id of the desired workbook to relocate.
    'server'        specified server address
    'auth_token'    authentication token that grants user access to API calls
    'user_id'       ID of user with access to workbook
    'site_id'       ID of the site that the user is signed into
    'workbook_name' name of workbook to get ID of
    Returns the workbook id and the project id that contains the workbook.
    """
    url = server + "/api/{0}/sites/{1}/tasks/extractRefreshes".format(VERSION, site_id)
    server_response = requests.get(url, headers={'x-tableau-auth': auth_token})
    _check_status(server_response, 200)
    xml_response = ET.fromstring(_encode_for_display(server_response.text))

    tasks = xml_response.findall('.//t:task', namespaces=xmlns)
    for task in tasks:
        schedule = task.find(".//t:schedule", namespaces=xmlns)
        obj = task.find(".//t:{0}".format(object_type), namespaces=xmlns)
        extractRefresh = task.find(".//t:extractRefresh", namespaces=xmlns)

        if obj is not None and schedule.get('id') == schedule_id and obj.get('id') == object_id:
            return extractRefresh.get('id')

    error = "Extract with schedule_id '{0}' and object_id '{1}' not found.".format(schedule_id, object_id)
    raise LookupError(error)

def run_extract_refresh_task(server, auth_token, site_id, extract_refresh_id):
    """
    Gets the id of the desired workbook to relocate.
    'server'        specified server address
    'auth_token'    authentication token that grants user access to API calls
    'user_id'       ID of user with access to workbook
    'site_id'       ID of the site that the user is signed into
    'schedule_name' name of schedule to get ID of
    Returns the workbook id and the project id that contains the workbook.
    """
    url = server + "/api/{0}/sites/{1}/tasks/extractRefreshes/{2}/runNow".format(VERSION, site_id, extract_refresh_id)


    # Builds the request
    xml_request = ET.Element('tsRequest')
    xml_request = ET.tostring(xml_request)

    # Make the request to server
    server_response = requests.post(url, data=xml_request, headers={'x-tableau-auth': auth_token})
    _check_status(server_response, 200)

    # ASCII encode server response to enable displaying to console
    server_response = _encode_for_display(server_response.text)

    # Reads and parses the response
    parsed_response = ET.fromstring(server_response)

    # Gets the auth token and site ID
    job_id = parsed_response.find('.//t:job', namespaces=xmlns).get('id')
    return job_id

def main():
    ##### STEP 0: Initialization #####
    if len(sys.argv) == 9:
        server = sys.argv[1]
        server_username = sys.argv[2]
        password = sys.argv[3]
        site = sys.argv[4]
        project_name = sys.argv[5]
        object_type = sys.argv[6]
        object_name = sys.argv[7]
        schedule_name = sys.argv[8]
    else:
        error = "8 arguments needed (server, username, password, site, project, object type <datasource|workbook>, object name, schedule name)"
        print(error)
        print("using defaults")
        server = "http://localhost"
        server_username = "admin"
        password = "admin"
        site = ""
        project_name = "Default"
        object_type = "workbook"
        object_name = "Book1"
        schedule_name = "End of the month"
        #raise UserDefinedFieldError(error)


    ##### STEP 1: Sign in #####
    print("\n1. Signing in as " + server_username)
    auth_token, site_id, user_id = sign_in(server, server_username, password, site)

    ##### STEP 2: Get id #####
    print("\n2. Finding id")

    project_id = get_project_id(server, auth_token, site_id, project_name)
    print(" Got project id: {0}".format(project_id))

    if object_type == 'datasource':
        object_id = get_datasource_id(server, auth_token, site_id, project_id, object_name)
        print(" Got object id: {0}".format(object_id))
    else:
        object_id = get_workbook_id(server, auth_token, user_id, site_id, project_id, object_name)
        print(" Got workbook id: {0}".format(object_id))

    schedule_id = get_schedule_id(server, auth_token, schedule_name)
    print(" Got schedule id: {0}".format(schedule_id))

    extract_refresh_id = get_extract_refresh_id(server, auth_token, site_id, schedule_id, object_type, object_id)
    print(" Got extract refresh id: {0}".format(extract_refresh_id))


    ##### STEP 3: Refresh extract #####
    print("\n3. Refreshing extract")
    job_id = run_extract_refresh_task(server, auth_token, site_id, extract_refresh_id)
    print("Extract refresh job_id: {0}".format(job_id))

    ##### STEP 4: Sign out #####
    print("\n4. Signing out and invalidating the authentication token")
    sign_out(server, auth_token)


if __name__ == "__main__":
    main()
