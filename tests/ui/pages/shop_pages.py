from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from .base_page import BasePage


class LoginPage(BasePage):
    def load(self):
        return self.open("/login")

    def login(self, email, password):
        self.type(By.ID, "email", email)
        self.type(By.ID, "password", password)
        self.click(By.ID, "login-btn")


class ProductsPage(BasePage):
    def load(self):
        return self.open("/products")

    def search(self, query):
        self.type(By.ID, "search-input", query)
        self.click(By.ID, "search-btn")
        self.wait.until(EC.url_contains("q="))

    def names(self):
        return [e.text for e in self.driver.find_elements(By.CSS_SELECTOR, "li.product .product-name")]

    def result_count(self):
        return self.find(By.ID, "result-count").text

    def add(self, name):
        self.click(By.CSS_SELECTOR, f'button.add-to-cart[data-name="{name}"]')

    def wait_for_cart_count(self, n):
        self.wait.until(EC.text_to_be_present_in_element((By.ID, "cart-count"), str(n)))
        return int(self.find(By.ID, "cart-count").text)

    def open_cart(self):
        self.click(By.ID, "cart-link")


class CartPage(BasePage):
    def rows(self):
        return [e.text for e in self.driver.find_elements(By.CSS_SELECTOR, "tr.cart-row .cart-name")]

    def total(self):
        return self.find(By.ID, "cart-total").text

    def remove_first(self):
        self.click(By.CSS_SELECTOR, "tr.cart-row .remove-btn")
        self.find(By.ID, "cart-empty")

    def checkout(self):
        self.click(By.ID, "checkout-link")


class CheckoutPage(BasePage):
    def place_order(self, name, address):
        self.type(By.ID, "full-name", name)
        self.type(By.ID, "address", address)
        self.click(By.ID, "place-order-btn")

    def outcome(self):
        """Wait for either the confirmation page or a validation error."""
        self.wait.until(lambda d: d.find_elements(By.ID, "order-confirmation")
                        or d.find_elements(By.ID, "flash-error"))
        if self.driver.find_elements(By.ID, "order-confirmation"):
            return "confirmed", self.find(By.ID, "order-id").text
        return "error", self.flash("error")
