package com.technova.payment.auth;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.function.Executable;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.Locale;
import java.util.stream.IntStream;

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

    @Test // (a) LR-2, matrix T02b: same length, so a length check alone can't reject it
    void sameLengthWrongPasswordShouldFail() {
        int last = VALID_PASS.length() - 1;
        char replacement = VALID_PASS.charAt(last) == '#' ? '$' : '#';
        String wrong = VALID_PASS.substring(0, last) + replacement;
        // Guards: same length, identical except for the last character
        assertEquals(VALID_PASS.length(), wrong.length());
        assertEquals(VALID_PASS.substring(0, last), wrong.substring(0, last));
        assertNotEquals(VALID_PASS.charAt(last), wrong.charAt(last));
        assertFalse(service.login(VALID_USER, wrong));
    }

    @Test // (b) LR-2 (password case-sensitivity is implied; spec ambiguity A1), matrix T05
    void passwordIsCaseSensitive() {
        String lower = VALID_PASS.toLowerCase(Locale.ROOT);
        String upper = VALID_PASS.toUpperCase(Locale.ROOT);
        // Guards: each variant differs from PW in case only
        assertNotEquals(VALID_PASS, lower);
        assertNotEquals(VALID_PASS, upper);
        assertTrue(VALID_PASS.equalsIgnoreCase(lower));
        assertTrue(VALID_PASS.equalsIgnoreCase(upper));
        assertAll(
                () -> assertFalse(service.login(VALID_USER, lower), "lowercase"),
                () -> assertFalse(service.login(VALID_USER, upper), "uppercase"));
    }

    @Test // (c) LR-2, matrix T03: every non-empty strict prefix (the empty one is LR-5)
    void strictPrefixOfPasswordShouldFail() {
        assertTrue(VALID_PASS.length() > 1, "PW must be long enough to have a non-empty strict prefix");
        assertAll(IntStream.range(1, VALID_PASS.length())
                .mapToObj(len -> VALID_PASS.substring(0, len))
                .map(prefix -> (Executable) () -> {
                    // Guards: a true strict prefix
                    assertTrue(prefix.length() < VALID_PASS.length());
                    assertTrue(VALID_PASS.startsWith(prefix));
                    assertFalse(service.login(VALID_USER, prefix), "prefix length " + prefix.length());
                }));
    }

    // (d) LR-8 (spec names only spaces; ambiguity A3), matrix T24/T26.
    // The display name leaves out the argument so tab/newline/NUL don't end up in the Surefire XML reports.
    @ParameterizedTest(name = "padding char #{index}")
    @ValueSource(strings = {"\t", "\n", "\0"})
    void controlCharacterPaddingShouldFail(String pad) {
        // Guards: exactly one control character, so each input is a valid value plus one char
        assertEquals(1, pad.length());
        assertTrue(Character.isISOControl(pad.charAt(0)));
        assertAll(
                () -> assertFalse(service.login(pad + VALID_USER, VALID_PASS), "leading on username"),
                () -> assertFalse(service.login(VALID_USER + pad, VALID_PASS), "trailing on username"),
                () -> assertFalse(service.login(VALID_USER, pad + VALID_PASS), "leading on password"),
                () -> assertFalse(service.login(VALID_USER, VALID_PASS + pad), "trailing on password"));
    }
}
