package com.technova.payment.auth;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

class UserRepositoryTest {
    private final UserRepository repository = new UserRepository();

    @Test
    void findsSyntheticDemoUser() {
        Optional<User> user = repository.findByUsername("demo.user");
        assertTrue(user.isPresent());
        assertEquals("demo.user", user.get().getUsername());
    }

    @Test
    void unknownUsernameReturnsEmpty() {
        assertTrue(repository.findByUsername("no.such.user").isEmpty());
    }

    @ParameterizedTest
    @ValueSource(strings = {"Demo.User", "DEMO.USER"})
    void lookupIsCaseSensitive(String username) {
        assertTrue(repository.findByUsername(username).isEmpty());
    }

    @ParameterizedTest
    @ValueSource(strings = {" demo.user", "demo.user "})
    void lookupDoesNotTrim(String username) {
        assertTrue(repository.findByUsername(username).isEmpty());
    }

    @ParameterizedTest
    @NullAndEmptySource
    void nullOrEmptyUsernameReturnsEmptyWithoutThrowing(String username) {
        assertTrue(assertDoesNotThrow(() -> repository.findByUsername(username)).isEmpty());
    }
}
