#!/usr/bin/env python3
import datetime
import json
import requests
import concurrent.futures
import flask
from flask import Flask, send_file, request, abort
from lxml import html
from argparse import ArgumentParser
from time import perf_counter

PORTAL_PATH = "html/page.html"
STYLE_PATH = "style/style.css"
SCRIPTS_PATH = "scripts/scripts.js"
LOADING_PATH = "assets/loading.gif"


RADIUS_BASE_URL = "https://radius.mathnasium.com"

RADIUS_LOGIN_URL, RADIUS_IM_URL, RADIUS_STUDENT_DATA_SOURCE = (
    RADIUS_BASE_URL + "/Account/Login",
    RADIUS_BASE_URL + "/AnswerKey/AnswerkeyCheckin/",
    RADIUS_BASE_URL + "/AnswerKey/GetStudentDataSource",
)

TEMPLATE_ASSESSMENT_NOT_COMPLETED = "templates/assessmentnc.txt"
TEMPLATE_HW_COMPLETED_GOOD_SESSION = "templates/hwcgoodsession.txt"
TEMPLATE_HW_COMPLETED_STRUGGLED = "templates/hwcstruggled.txt"
TEMPLATE_HW_NOT_COMPLETED_GOOD_SESSION = "templates/hwncgoodsession.txt"
TEMPLATE_HW_NOT_COMPLETED_STRUGGLED = "templates/hwncstruggled.txt"
TEMPLATE_NO_HW_GOOD_SESSION = "templates/nohwgoodsession.txt"
TEMPLATE_NO_HW_STRUGGLED = "templates/nohwstruggled.txt"
TEMPLATE_POST_COMPLETED = "templates/postcomplete.txt"
TEMPLATE_PRE_COMPLETED = "templates/precomplete.txt"


http_server = Flask(__name__)


class CodeTimer:
    def __init__(self, msg="Took {:0.2f}s", prefix=""):
        self.start = 0
        self.msg = prefix + msg

    def __enter__(self):
        self.start = perf_counter()

    def __exit__(self, exception_type, exception_value, traceback):
        print(self.msg.format(perf_counter() - self.start))


def make_template(
    student_name, instructors, pages, hw, hwcomplete, assessment, post_c, pre_c, notes
):
    def select_template():
        if assessment == True:
            if post_c == True:
                return TEMPLATE_POST_COMPLETED
            if pre_c == True:
                return TEMPLATE_PRE_COMPLETED
            else:
                return TEMPLATE_ASSESSMENT_NOT_COMPLETED
        if hw == True:
            if hwcomplete == True:
                if pages > 2:
                    return TEMPLATE_HW_COMPLETED_GOOD_SESSION
                else:
                    return TEMPLATE_HW_COMPLETED_STRUGGLED
            else:
                if pages > 2:
                    return TEMPLATE_HW_NOT_COMPLETED_GOOD_SESSION
                else:
                    return TEMPLATE_HW_NOT_COMPLETED_STRUGGLED
        else:
            if pages > 2:
                return TEMPLATE_NO_HW_GOOD_SESSION
            else:
                return TEMPLATE_NO_HW_STRUGGLED

    with open(select_template(), "r") as rfile:
        template = rfile.read().strip()
        return template.format(
            iname=instructors,
            sname=student_name,
            pages=pages,
            snotes=notes,
        )


def dwp_to_student_row(dwp):
    def get_checked_element_value(elem):
        if "checked" in elem.attrib:
            return elem.attrib["checked"] == "checked"
        else:
            return False

    def find_pages():
        js = dwp.xpath('//script[@type="text/javascript"]')[0]
        js_lines = js.text_content().split("\n")

        idx = 0
        for k, i in enumerate(js_lines):
            if "NumberOfPagesCompleted" in i:
                idx = k
                break

        for i in js_lines[idx : idx + 10]:
            if "value: parseInt(" in i:
                s = "".join(ch for ch in i if ch.isdigit())
                return int(s) if s is not None and s != "" else 0

    # Student is a span with              id = student-name
    # Session date is a span with         id = sessdatestr
    # Instructor names in a span with     id = instructor-names
    # Session start time is an input with id = SessionStartTime
    # Session end time is an input with   id = SessionEndTime
    # Num of pages is an input with       id = NumberOfPagesCompleted
    # Homework y/n is an input with       id = Schoolwork
    # Session notes is a text area with   id = SessionNotes
    snotes = dwp.get_element_by_id("SessionNotes").text
    student_name = dwp.get_element_by_id("student-name").text
    date = dwp.get_element_by_id("sessdatestr").text
    instructors = dwp.get_element_by_id("instructor-names").text

    # session_start_time = dwp.get_element_by_id("SessionStartTime").text
    # session_end_time = dwp.get_element_by_id("SessionEndTime").text

    pages = find_pages()

    homework = get_checked_element_value(dwp.get_element_by_id("Schoolwork"))

    hcomplete = False
    if homework:
        # Homework complete is an input with  id = SchoolworkCompleted
        hcomplete = get_checked_element_value(
            dwp.get_element_by_id("SchoolworkCompleted")
        )

    # Assessment y/n is an input with     id = StudentWorkedOnAnAssessmentToday
    assessment = get_checked_element_value(
        dwp.get_element_by_id("StudentWorkedOnAnAssessmentToday")
    )

    post_c = False
    pre_c = False
    # post_ip = False
    # pre_ip = False
    if assessment:
        # Completed a post is an input with   id = CompletedAPost
        post_c = get_checked_element_value(dwp.get_element_by_id("CompletedAPost"))

        # Completed a pre is an input with    id = CompletedAPre
        pre_c = get_checked_element_value(dwp.get_element_by_id("CompletedAPre"))

        ## Post in progress is an input with   id = PostInProgress
        # post_ip = get_checked_element_value(dwp.get_element_by_id("PostInProgress"))
        #
        ## Pre in progress is an input with    id = PreInProgress
        # pre_ip = get_checked_element_value(dwp.get_element_by_id("PreInProgress"))

    return {
        "Student": student_name,
        "Date": date,
        "Template": make_template(
            student_name=student_name,
            instructors=instructors,
            pages=pages,
            hw=homework,
            hwcomplete=hcomplete,
            assessment=assessment,
            post_c=post_c,
            pre_c=pre_c,
            notes=snotes,
        ),
    }


def get_token(page):
    token_elem = page.xpath('//input[@name="__RequestVerificationToken"]')
    if len(token_elem) == 0:
        print("Failed to find authentication verification token0")
        return False
    return token_elem[0].attrib["value"]


def perform_login(user, passwd):
    with CodeTimer("Took {:.2f}s to login"):
        with requests.Session() as cl:
            # Find element with name=__RequestVerificationToken
            login_page_response = cl.get(RADIUS_LOGIN_URL)
            login_page = html.fromstring(login_page_response.content)
            token = get_token(login_page)

            # Perform login, sending username, password, and authentication code
            login_attempt = cl.post(
                RADIUS_LOGIN_URL,
                data={
                    "UserName": user,
                    "Password": passwd,
                    "__RequestVerificationToken": token,
                    "ReturnUrl": "/",
                },
            )
            return cl.cookies, login_attempt.ok


def get_student_data(cookies):
    def get_page_async(cl, url):
        page = cl.get(url)
        return page.content

    def map_pages_to_student_rows(cl, manifest):
        response_list = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for i in manifest:
                arrival_time = float(i["ArrivalTime"][6:-2]) / 1000
                date = datetime.datetime.fromtimestamp(arrival_time)
                if date < (datetime.datetime.now() - datetime.timedelta(days=1)):
                    continue

                params = (
                    "/DigitalWorkoutPlan/_Index/?studentId={}&attendanceId={}".format(
                        i["StudentId"], i["AttendanceId"]
                    )
                )
                dwp_url = RADIUS_BASE_URL + params
                futures.append(executor.submit(get_page_async, cl=cl, url=dwp_url))

            for future in concurrent.futures.as_completed(futures):
                response_list.append(
                    dwp_to_student_row(html.fromstring(future.result()))
                )

        return response_list

    with requests.Session() as cl:
        # Update authentication cookies
        cl.cookies.update(cookies)
        im_page_response = cl.get(RADIUS_IM_URL)
        im_page = html.fromstring(im_page_response.content)

        token = get_token(im_page)

        data_source = cl.post(
            RADIUS_STUDENT_DATA_SOURCE,
            data={"__RequestVerificationToken": token},
        )

        student_manifest = data_source.json()["DataSource"]

        with CodeTimer("Took {:.2f}s to load students"):
            return map_pages_to_student_rows(cl, student_manifest)


# Route portal HTML, CSS and JS to client
@http_server.route("/", methods=["GET"])
def portal():
    return send_file(PORTAL_PATH)


@http_server.route("/style.css", methods=["GET"])
def css():
    return send_file(STYLE_PATH)


@http_server.route("/scripts.js", methods=["GET"])
def scripts():
    return send_file(SCRIPTS_PATH)


@http_server.route("/loading.gif", methods=["GET"])
def loading():
    return send_file(LOADING_PATH)


# Send message API call
@http_server.route("/send_message", methods=["POST"])
def send_message():
    return "Response body goes here..."


@http_server.route("/scrape_radius", methods=["GET"])
def scrape_radius():
    user = request.args["user"]
    pswd = request.args["passwd"]
    if user is None or pswd is None:
        abort(401)

    cookies, login_ok = perform_login(user, pswd)

    if not login_ok:
        abort(401)

    return json.dumps(get_student_data(cookies))


# Setup argument parsing
parser = ArgumentParser()
parser.add_argument("--port", help="Port to bind HTTP server", type=int, default=8080)
parser.add_argument(
    "--host", help="Address to bind HTTP server", type=str, default="localhost"
)


# Application entry point
def main(args):
    print("Flask Version: {}".format(flask.__version__))
    http_server.run(args.host, args.port)


if __name__ == "__main__":
    args = parser.parse_args()
    main(args)
