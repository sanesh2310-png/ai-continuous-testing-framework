import pytest

from shop.app import TEST_EMAIL, TEST_PASSWORD

pytestmark = pytest.mark.ui
GOOD_ADDRESS = "12 MG Road, Bengaluru 560001"


@pytest.mark.case("UI-001", "User Login", expected="Products page opens and shows the user's email",
                  category="Authentication", severity="Critical")
@pytest.mark.smoke
def test_login(login_page, products_page):
    login_page.load().login(TEST_EMAIL, TEST_PASSWORD)
    assert products_page.welcome() == TEST_EMAIL
    assert products_page.path == "/products", f"Expected /products but was {products_page.path}"


@pytest.mark.case("UI-002", "Login With Wrong Password", expected="Error: Invalid email or password",
                  category="Authentication", severity="High")
def test_login_wrong_password(login_page):
    login_page.load().login(TEST_EMAIL, "WrongPass1")
    assert "Invalid email or password" in login_page.flash("error")


@pytest.mark.case("UI-003", "Login Input Validation", expected="Validation message is displayed",
                  category="Input Validation", severity="Medium")
@pytest.mark.parametrize("email,password,message", [
    ("not-an-email", "Test@123", "valid email"),
    ("tester@shop.com", "123", "at least 6"),
    ("", "", "required"),
], ids=["bad-email", "short-password", "empty-fields"])
def test_login_validation(login_page, email, password, message):
    login_page.load().login(email, password)
    assert message in login_page.flash("error")


@pytest.mark.case("UI-004", "Protected Page Requires Login", expected="Redirect to /login",
                  category="Authentication", severity="High")
def test_protected_page_redirects(products_page):
    products_page.load()
    assert products_page.path == "/login", f"Expected /login but was {products_page.path}"


@pytest.mark.case("UI-005", "Product Search", expected="Only laptop products are listed",
                  category="Search", severity="Medium")
def test_product_search(logged_in, products_page):
    products_page.search("laptop")
    names = products_page.names()
    assert names and all("laptop" in n.lower() for n in names), f"Unexpected results: {names}"


@pytest.mark.case("UI-006", "Search With No Results", expected="0 product(s) found",
                  category="Search", severity="Low")
def test_search_no_results(logged_in, products_page):
    products_page.search("zzzz")
    assert products_page.result_count() == "0 product(s) found"


@pytest.mark.case("UI-007", "Add Product to Cart", expected="Cart counter becomes 1",
                  category="Cart", severity="High")
def test_add_to_cart(logged_in, products_page):
    products_page.add("Wireless Mouse")
    assert products_page.wait_for_cart_count(1) == 1


@pytest.mark.case("UI-008", "Cart Total Calculation", expected="Total is ₹2,698 for mouse + USB-C hub",
                  category="Cart", severity="High")
def test_cart_total(logged_in, products_page, cart_page):
    products_page.add("Wireless Mouse")
    products_page.wait_for_cart_count(1)
    products_page.add("USB-C Hub")
    products_page.wait_for_cart_count(2)
    products_page.open_cart()
    assert "2,698" in cart_page.total(), f"Unexpected total: {cart_page.total()}"


@pytest.mark.case("UI-009", "Remove Product From Cart", expected="Cart shows it is empty",
                  category="Cart", severity="Medium")
def test_remove_from_cart(logged_in, products_page, cart_page):
    products_page.add("Webcam HD")
    products_page.wait_for_cart_count(1)
    products_page.open_cart()
    cart_page.remove_first()
    assert cart_page.rows() == []


@pytest.mark.case("UI-010", "Checkout With Valid Details", expected="Order confirmation is shown",
                  category="Checkout", severity="Critical")
@pytest.mark.smoke
def test_checkout_valid(logged_in, products_page, cart_page, checkout_page):
    products_page.add("Laptop Stand")
    products_page.wait_for_cart_count(1)
    products_page.open_cart()
    cart_page.checkout()
    checkout_page.place_order("Deeksha", GOOD_ADDRESS)
    kind, text = checkout_page.outcome()
    assert kind == "confirmed", f"Expected an order confirmation but got error: {text}"


@pytest.mark.case("UI-011", "Checkout with Invalid Address",
                  expected="Validation error appears and the order is not placed",
                  category="Input Validation", severity="High")
def test_checkout_invalid_address(logged_in, products_page, cart_page, checkout_page):
    products_page.add("Laptop Stand")
    products_page.wait_for_cart_count(1)
    products_page.open_cart()
    cart_page.checkout()
    checkout_page.place_order("Deeksha", "abc")
    kind, text = checkout_page.outcome()
    assert kind == "error", f"Expected a validation error but the order was submitted ({text})"
    assert "valid delivery address" in text


@pytest.mark.case("UI-012", "Logout", expected="Login page with a logged-out message",
                  category="Authentication", severity="Medium")
def test_logout(logged_in, products_page, login_page, home):
    products_page.logout()
    assert "logged out" in login_page.flash("success")
    products_page.load()
    assert products_page.path == "/login"
