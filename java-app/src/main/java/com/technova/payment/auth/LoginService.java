package com.technova.payment.auth;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * Authenticates a username/password pair against {@link UserRepository}.
 * Behaviour follows rag/knowledge/login_requirements.md (LR-1..LR-8, ASSUMPTION).
 */
public class LoginService {

    private final UserRepository userRepository;

    public LoginService() {
        this.userRepository = new UserRepository();
    }

    /**
     * @return true only for an exact (case-sensitive, untrimmed) username and password match;
     *         false for anything else, including null/empty/whitespace-only input. Never throws.
     */
    public boolean login(String username, String password) {
        if (isBlank(username) || isBlank(password)) {      // LR-4, LR-5, LR-6
            return false;
        }
        return userRepository.findByUsername(username)     // LR-3, LR-7, LR-8 (exact key, no trim)
                .map(user -> passwordMatches(user.getPassword(), password)) // LR-1, LR-2, LR-8
                .orElse(false);
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }

    private static boolean passwordMatches(String stored, String supplied) {
        if (stored == null) {
            return false;
        }
        return MessageDigest.isEqual(
                stored.getBytes(StandardCharsets.UTF_8),
                supplied.getBytes(StandardCharsets.UTF_8));
    }
}
