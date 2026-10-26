"""Selenium fixtures.

BASE_URL            -> test an already running app (CI / Docker). Otherwise the
                       shop is started on a free port in a background thread.
SELENIUM_REMOTE_URL -> use a remote Selenium (docker-compose); otherwise local Chrome.
HEADED=1            -> show the browser window.
BROWSER=firefox     -> use Firefox instead of Chrome (default: chrome).
SHOP_BUGS           -> switch on deliberate defects in the shop (see shop/app.py).
"""
import os
import threading

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from werkzeug.serving import make_server

from shop.app import TEST_EMAIL, TEST_PASSWORD, create_app
from tests.ui.pages.base_page import BasePage
from tests.ui.pages.shop_pages import CartPage, CheckoutPage, LoginPage, ProductsPage


@pytest.fixture(scope="session")
def base_url():
    external = os.environ.get("BASE_URL")
    if external:
        yield external
        return
    # threaded=True matters: Chrome opens idle speculative connections that would
    # otherwise block a single-threaded server and make pages hang.
    server = make_server("127.0.0.1", 0, create_app({"TESTING": True}), threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def _options():
    opts = Options()
    if not os.environ.get("HEADED"):
        opts.add_argument("--headless=new")
    for arg in ("--no-sandbox", "--disable-dev-shm-usage", "--window-size=1280,900"):
        opts.add_argument(arg)
    return opts


def _firefox_options():
    opts = FirefoxOptions()
    if not os.environ.get("HEADED"):
        opts.add_argument("-headless")
    opts.add_argument("--width=1280")
    opts.add_argument("--height=900")
    if os.environ.get("FIREFOX_BINARY"):
        opts.binary_location = os.environ["FIREFOX_BINARY"]
    return opts


@pytest.fixture
def driver():
    remote = os.environ.get("SELENIUM_REMOTE_URL")
    firefox = os.environ.get("BROWSER", "chrome").lower() == "firefox"
    try:
        if remote:
            drv = webdriver.Remote(command_executor=remote,
                                   options=_firefox_options() if firefox else _options())
        elif firefox:
            drv = webdriver.Firefox(options=_firefox_options())
        else:
            drv = webdriver.Chrome(options=_options())
    except Exception as exc:
        raise RuntimeError(f"Browser could not start (is Chrome installed?): {str(exc).splitlines()[0]}") from exc
    yield drv
    drv.quit()


@pytest.fixture
def login_page(driver, base_url):
    return LoginPage(driver, base_url)


@pytest.fixture
def products_page(driver, base_url):
    return ProductsPage(driver, base_url)


@pytest.fixture
def cart_page(driver, base_url):
    return CartPage(driver, base_url)


@pytest.fixture
def checkout_page(driver, base_url):
    return CheckoutPage(driver, base_url)


@pytest.fixture
def home(driver, base_url):
    return BasePage(driver, base_url)


@pytest.fixture
def logged_in(login_page, products_page):
    login_page.load().login(TEST_EMAIL, TEST_PASSWORD)
    products_page.welcome()  # wait until the products page is shown
    return TEST_EMAIL
