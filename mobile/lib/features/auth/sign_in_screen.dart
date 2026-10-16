import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart' show AuthException;

import '../../api/errors.dart';
import '../../app/env.dart';
import '../../state/app_state.dart';
import '../../theme/colors.dart';
import '../../widgets/buttons.dart';
import '../../widgets/surfaces.dart';

/// Sign in / sign up — the port of `frontend/src/pages/SignIn.jsx`.
///
/// Same account system as the website: Supabase authenticates, the backend
/// issues its own session. Someone who signed up on banterclips.com signs in
/// here with the same credentials, and sees the same clips.
class SignInScreen extends ConsumerStatefulWidget {
  const SignInScreen({super.key});

  @override
  ConsumerState<SignInScreen> createState() => _SignInScreenState();
}

enum _Mode { signIn, signUp, forgot }

class _SignInScreenState extends ConsumerState<SignInScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _name = TextEditingController();
  final _formKey = GlobalKey<FormState>();

  _Mode _mode = _Mode.signIn;
  bool _busy = false;
  bool _obscure = true;
  String _error = '';
  String _notice = '';

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _name.dispose();
    super.dispose();
  }

  /// Every auth action funnels through here so the busy flag, the error line
  /// and the "mounted" check are written once rather than five times.
  Future<void> _run(Future<void> Function() action) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = '';
      _notice = '';
    });
    try {
      await action();
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (e) {
      if (mounted) setState(() => _error = readableAuthError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _submit() {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    final email = _email.text.trim();
    final notifier = ref.read(appStateProvider.notifier);

    switch (_mode) {
      case _Mode.signIn:
        _run(
          () => notifier.signInWithPassword(
            email: email,
            password: _password.text,
          ),
        );
      case _Mode.signUp:
        _run(() async {
          final signedIn = await notifier.signUp(
            email: email,
            password: _password.text,
            displayName: _name.text,
          );
          // With email confirmation on there is no session yet. Say so —
          // silently doing nothing is how people conclude an app is broken.
          if (!signedIn && mounted) {
            setState(() {
              _mode = _Mode.signIn;
              _notice = 'Check $email for a confirmation link, then sign in.';
            });
          }
        });
      case _Mode.forgot:
        _run(() async {
          await notifier.sendPasswordReset(email);
          if (mounted) {
            setState(() {
              _mode = _Mode.signIn;
              _notice = 'Password reset link sent to $email.';
            });
          }
        });
    }
  }

  @override
  Widget build(BuildContext context) {
    final isSignUp = _mode == _Mode.signUp;
    final isForgot = _mode == _Mode.forgot;
    final authError = ref.watch(
      appStateProvider.select((state) => state.authError),
    );

    return Scaffold(
      // The keyboard covers half the screen on a phone; the body scrolls
      // under it instead of the layout overflowing.
      resizeToAvoidBottomInset: true,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 28),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const _Wordmark(),
                    const SizedBox(height: 28),
                    Text(
                      isForgot
                          ? 'Reset your password'
                          : isSignUp
                          ? 'Create your account'
                          : 'Welcome back',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      isForgot
                          ? "We'll email you a link to set a new one."
                          : isSignUp
                          ? '60 welcome credits, no card needed.'
                          : 'Sign in to keep making clips.',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                    const SizedBox(height: 26),

                    if (_notice.isNotEmpty) ...[
                      Notice.success(_notice),
                      const SizedBox(height: 14),
                    ],
                    if (_error.isNotEmpty) ...[
                      Notice.error(_error),
                      const SizedBox(height: 14),
                    ],
                    if (_error.isEmpty && authError.isNotEmpty) ...[
                      Notice.error(authError),
                      const SizedBox(height: 14),
                    ],

                    if (isSignUp) ...[
                      TextFormField(
                        controller: _name,
                        textInputAction: TextInputAction.next,
                        textCapitalization: TextCapitalization.words,
                        decoration: const InputDecoration(
                          labelText: 'Display name',
                          hintText: 'Optional',
                        ),
                      ),
                      const SizedBox(height: 12),
                    ],

                    TextFormField(
                      controller: _email,
                      keyboardType: TextInputType.emailAddress,
                      autocorrect: false,
                      textInputAction: isForgot
                          ? TextInputAction.done
                          : TextInputAction.next,
                      autofillHints: const [AutofillHints.email],
                      decoration: const InputDecoration(labelText: 'Email'),
                      validator: (value) {
                        final text = value?.trim() ?? '';
                        if (text.isEmpty) return 'Enter your email';
                        if (!text.contains('@') || !text.contains('.')) {
                          return "That doesn't look like an email";
                        }
                        return null;
                      },
                    ),

                    if (!isForgot) ...[
                      const SizedBox(height: 12),
                      TextFormField(
                        controller: _password,
                        obscureText: _obscure,
                        textInputAction: TextInputAction.done,
                        onFieldSubmitted: (_) => _submit(),
                        autofillHints: [
                          isSignUp
                              ? AutofillHints.newPassword
                              : AutofillHints.password,
                        ],
                        decoration: InputDecoration(
                          labelText: 'Password',
                          suffixIcon: IconButton(
                            icon: Icon(
                              _obscure
                                  ? Icons.visibility_off_outlined
                                  : Icons.visibility_outlined,
                              color: AppColors.muted,
                              size: 20,
                            ),
                            onPressed: () =>
                                setState(() => _obscure = !_obscure),
                          ),
                        ),
                        validator: (value) {
                          final text = value ?? '';
                          if (text.isEmpty) return 'Enter your password';
                          // Supabase's own minimum. Catching it here saves a
                          // round-trip and a less friendly server message.
                          if (isSignUp && text.length < 6) {
                            return 'At least 6 characters';
                          }
                          return null;
                        },
                      ),
                    ],

                    if (_mode == _Mode.signIn)
                      Align(
                        alignment: Alignment.centerRight,
                        child: TextAction(
                          label: 'Forgot password?',
                          fontSize: 12.5,
                          color: AppColors.muted,
                          onPressed: () => setState(() {
                            _mode = _Mode.forgot;
                            _error = '';
                          }),
                        ),
                      ),

                    const SizedBox(height: 16),
                    GradButton(
                      label: isForgot
                          ? 'Send reset link'
                          : isSignUp
                          ? 'Create account'
                          : 'Sign in',
                      loading: _busy,
                      onPressed: _submit,
                    ),

                    if (!isForgot) ...[
                      const SizedBox(height: 18),
                      const _OrDivider(),
                      const SizedBox(height: 18),
                      GhostButton(
                        label: 'Continue with Google',
                        icon: Icons.g_mobiledata_rounded,
                        onPressed: _busy
                            ? null
                            : () => _run(
                                ref
                                    .read(appStateProvider.notifier)
                                    .signInWithGoogle,
                              ),
                      ),
                      const SizedBox(height: 10),
                      GhostButton(
                        label: 'Email me a sign-in link',
                        icon: Icons.mail_outline_rounded,
                        color: AppColors.muted,
                        onPressed: _busy
                            ? null
                            : () {
                                if (!(_formKey.currentState?.validate() ??
                                    false)) {
                                  return;
                                }
                                _run(() async {
                                  await ref
                                      .read(appStateProvider.notifier)
                                      .sendMagicLink(_email.text.trim());
                                  if (mounted) {
                                    setState(
                                      () => _notice =
                                          'Sign-in link sent to ${_email.text.trim()}.',
                                    );
                                  }
                                });
                              },
                      ),
                    ],

                    // The offline development path: with no Supabase keys
                    // compiled in, the only way to sign in is the backend's
                    // dev magic-link, which needs DEV_MODE=true.
                    if (!Env.supabaseEnabled) ...[
                      const SizedBox(height: 16),
                      const Notice(
                        text:
                            'Development build — signing in through the local '
                            'backend, which must be running with DEV_MODE=true.',
                        icon: Icons.construction_rounded,
                      ),
                      const SizedBox(height: 10),
                      GhostButton(
                        label: 'Dev sign-in',
                        onPressed: _busy
                            ? null
                            : () {
                                if (!(_formKey.currentState?.validate() ??
                                    false)) {
                                  return;
                                }
                                _run(
                                  () => ref
                                      .read(appStateProvider.notifier)
                                      .devSignIn(_email.text.trim()),
                                );
                              },
                      ),
                    ],

                    const SizedBox(height: 22),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          isSignUp
                              ? 'Already have an account?'
                              : "New to BanterClips?",
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        TextAction(
                          label: isSignUp ? 'Sign in' : 'Create one',
                          onPressed: () => setState(() {
                            _mode = isSignUp ? _Mode.signIn : _Mode.signUp;
                            _error = '';
                            _notice = '';
                          }),
                        ),
                      ],
                    ),
                    if (isForgot)
                      TextAction(
                        label: '← Back to sign in',
                        color: AppColors.muted,
                        onPressed: () => setState(() => _mode = _Mode.signIn),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Turn whatever Supabase threw into a sentence a person can act on.
///
/// `AuthException.toString()` is `AuthApiException(message: …, statusCode:
/// …, code: …)` — developer output, which is exactly what used to reach the
/// screen. The `code` is the stable part; the message is the fallback.
String readableAuthError(Object error) {
  if (error is AuthException) {
    switch (error.code) {
      case 'invalid_credentials':
        return "That email and password don't match. Try again, or reset your password.";
      case 'email_not_confirmed':
        return 'Confirm your email first — check your inbox for the link we sent.';
      case 'user_already_exists':
      case 'email_exists':
        return 'An account with that email already exists. Sign in instead.';
      case 'weak_password':
        return 'Pick a stronger password — at least 6 characters.';
      case 'over_email_send_rate_limit':
      case 'over_request_rate_limit':
        return 'Too many attempts — wait a minute and try again.';
      case 'validation_failed':
        return "That doesn't look like a valid email address.";
      case 'user_not_found':
        return 'No account with that email. Create one to get started.';
      case 'signup_disabled':
        return 'Sign-ups are closed right now.';
      case 'provider_disabled':
        return 'That sign-in method is not available right now.';
      case 'flow_state_expired':
      case 'flow_state_not_found':
      case 'otp_expired':
        return 'That link has expired — request a new one.';
    }
    final message = error.message.trim();
    if (message.toLowerCase().contains('invalid login')) {
      return "That email and password don't match. Try again, or reset your password.";
    }
    if (message.toLowerCase().contains('network') ||
        message.toLowerCase().contains('socket')) {
      return "Can't reach the sign-in service. Check your connection.";
    }
    return message.isEmpty
        ? 'Sign-in failed. Please try again.'
        : message[0].toUpperCase() + message.substring(1);
  }
  final text = error.toString();
  if (text.contains('SocketException') || text.contains('Failed host lookup')) {
    return "Can't reach the sign-in service. Check your connection.";
  }
  return 'Something went wrong signing you in. Please try again.';
}

class _Wordmark extends StatelessWidget {
  const _Wordmark();

  @override
  Widget build(BuildContext context) => Image.asset(
    'assets/images/banterclips-logo.png',
    width: 132,
    height: 132,
    filterQuality: FilterQuality.high,
  );
}

class _OrDivider extends StatelessWidget {
  const _OrDivider();

  @override
  Widget build(BuildContext context) => const Row(
    children: [
      Expanded(child: Divider(color: AppColors.border)),
      Padding(
        padding: EdgeInsets.symmetric(horizontal: 12),
        child: Text(
          'or',
          style: TextStyle(fontSize: 12, color: AppColors.muted2),
        ),
      ),
      Expanded(child: Divider(color: AppColors.border)),
    ],
  );
}
