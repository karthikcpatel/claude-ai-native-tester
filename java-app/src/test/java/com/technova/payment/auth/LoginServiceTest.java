package com.technova.payment.auth;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;

import static org.junit.jupiter.api.Assertions.*;

/** Spec (ASSUMPTION): rag/knowledge/login_requirements.md */
class LoginServiceTest {
    private static final String VALID_USER = "demo.user";
    private static final String VALID_PASS = "DemoPass123!";
    private final LoginService service = new LoginService();

    @Test // LR-1
    void loginWithValidCredentialsShouldSucceed() {
        assertTrue(service.login(VALID_USER, VALID_PASS));
    }

    @Test // LR-2
    void loginWithInvalidPasswordShouldFail() {
        assertFalse(service.login(VALID_USER, "WrongPass123!"));
    }

    @Test // LR-3
    void loginWithUnknownUsernameShouldFail() {
        assertFalse(service.login("no.such.user", VALID_PASS));
    }

    @ParameterizedTest // LR-4, LR-6
    @NullAndEmptySource
    @ValueSource(strings = {" ", "   ", "\t", "\n"})
    void blankUsernameShouldFailWithoutThrowing(String username) {
        assertFalse(assertDoesNotThrow(() -> service.login(username, VALID_PASS)));
    }

    @ParameterizedTest // LR-5, LR-6
    @NullAndEmptySource
    @ValueSource(strings = {" ", "   ", "\t", "\n"})
    void blankPasswordShouldFailWithoutThrowing(String password) {
        assertFalse(assertDoesNotThrow(() -> service.login(VALID_USER, password)));
    }

    @Test // LR-6
    void bothNullShouldFailWithoutThrowing() {
        assertFalse(assertDoesNotThrow(() -> service.login(null, null)));
    }

    @ParameterizedTest // LR-7
    @ValueSource(strings = {"Demo.User", "DEMO.USER"})
    void usernameIsCaseSensitive(String username) {
        assertFalse(service.login(username, VALID_PASS));
    }

    @ParameterizedTest // LR-8
    @ValueSource(strings = {" demo.user", "demo.user "})
    void usernameIsNotTrimmed(String username) {
        assertFalse(service.login(username, VALID_PASS));
    }

    @ParameterizedTest // LR-8
    @ValueSource(strings = {" DemoPass123!", "DemoPass123! "})
    void passwordIsNotTrimmed(String password) {
        assertFalse(service.login(VALID_USER, password));
    }
}
