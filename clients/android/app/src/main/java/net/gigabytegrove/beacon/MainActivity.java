package net.gigabytegrove.beacon;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.util.Base64;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * LAN-first native Beacon Android client.
 * No remote push dependency. Polling is active only while this Activity is visible.
 */
public final class MainActivity extends Activity {
    private static final int BACKGROUND = Color.rgb(15, 28, 46);
    private static final int SURFACE = Color.rgb(30, 52, 78);
    private static final int TEXT = Color.rgb(235, 244, 255);
    private static final int MUTED = Color.rgb(163, 189, 214);
    private static final long REFRESH_MS = 3500L;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Map<Integer, Integer> previousUnread = new HashMap<>();
    private final Set<Integer> rendered = new HashSet<>();
    private final ArrayList<JSONObject> knownBuddies = new ArrayList<>();
    private final ArrayList<JSONObject> knownGroups = new ArrayList<>();
    private SecureSession session;
    private String server = "";
    private String token;
    private int myUserId;
    private Integer activeBuddy;
    private String activeName = "";
    private boolean foreground;
    private boolean initializedUnread;
    private long lastTyping;
    private String currentStatus = "available";
    private boolean authenticated = false;
    private String lastRosterFingerprint = "";
    private LinearLayout root;
    private LinearLayout rosterList;
    private LinearLayout messagesList;
    private ScrollView messageScroll;
    private EditText inputMessage;
    private TextView typingLabel;
    private TextView errorLabel;
    private final Runnable ticker = new Runnable() {
        @Override public void run() {
            if (!foreground || token == null) return;
            poll();
            handler.postDelayed(this, REFRESH_MS);
        }
    };

    private interface Task<T> { T perform() throws Exception; }
    private interface Done<T> { void accept(T value, Exception error); }

    private <T> void async(Task<T> task, Done<T> callback) {
        worker.submit(() -> {
            T value = null;
            Exception failure = null;
            try { value = task.perform(); }
            catch (Exception error) { failure = error; }
            final T result = value;
            final Exception problem = failure;
            handler.post(() -> {
                if (isFinishing() || isDestroyed()) return;
                if (problem != null && "Your session has expired".equals(problem.getMessage())) {
                    token = null;
                    authenticated = false;
                    session.clear();
                    stopMonitor();
                    loginScreen("Session expired. Please sign in again.");
                    return;
                }
                callback.accept(result, problem);
            });
        });
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        session = new SecureSession(this);
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            manager.createNotificationChannel(new NotificationChannel(
                    "beacon_messages", "Beacon messages", NotificationManager.IMPORTANCE_DEFAULT));
        }
        if (Build.VERSION.SDK_INT >= 33 &&
                checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 400);
        }
        String[] previous = session.load();
        if (previous != null) {
            server = previous[0]; token = previous[1];
            async(() -> request("/me", "GET", null), (data, error) -> {
                if (error != null) {
                    session.clear(); token = null; stopMonitor(); loginScreen("Sign in to Beacon");
                } else {
                    myUserId = ((JSONObject) data).optInt("id");
                    authenticated = true;
                    currentStatus = getSharedPreferences(BeaconMonitorService.PREFS, MODE_PRIVATE)
                            .getString("status", "available");
                    ensureMonitorIfEnabled();
                    rosterScreen();
                    restartTicker();
                }
            });
            loginScreen("Restoring your session…");
        } else loginScreen("");
    }

    @Override protected void onResume() {
        super.onResume();
        foreground = true;
        getSharedPreferences(BeaconMonitorService.PREFS, MODE_PRIVATE)
                .edit().putBoolean("activity_visible", true).apply();
        restartTicker();
    }

    @Override protected void onPause() {
        foreground = false;
        getSharedPreferences(BeaconMonitorService.PREFS, MODE_PRIVATE)
                .edit().putBoolean("activity_visible", false).apply();
        handler.removeCallbacks(ticker);
        super.onPause();
    }

    @Override protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        worker.shutdownNow();
        super.onDestroy();
    }

    private void restartTicker() {
        handler.removeCallbacks(ticker);
        if (foreground && authenticated && token != null && root != null) handler.post(ticker);
    }

    private Object request(String path, String method, JSONObject data) throws Exception {
        URL endpoint = new URL(server + "/api" + path);
        HttpURLConnection connection = (HttpURLConnection) endpoint.openConnection();
        connection.setConnectTimeout(7000);
        connection.setReadTimeout(7000);
        connection.setRequestMethod(method);
        connection.setRequestProperty("Accept", "application/json");
        if (token != null) connection.setRequestProperty("Authorization", "Bearer " + token);
        connection.setUseCaches(false);
        try {
            if (data != null) {
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                try (OutputStream out = connection.getOutputStream()) {
                    out.write(data.toString().getBytes(StandardCharsets.UTF_8));
                }
            }
            int status = connection.getResponseCode();
            if (status == 401 && !"/login".equals(path))
                throw new Exception("Your session has expired");
            InputStream stream = status >= 400 ? connection.getErrorStream() : connection.getInputStream();
            byte[] bytes = new byte[0];
            if (stream != null) {
                try (InputStream in = stream; ByteArrayOutputStream buffer = new ByteArrayOutputStream()) {
                    byte[] chunk = new byte[4096];
                    int size;
                    while ((size = in.read(chunk)) != -1) buffer.write(chunk, 0, size);
                    bytes = buffer.toByteArray();
                }
            }
            String body = new String(bytes, StandardCharsets.UTF_8);
            Object json = body.trim().startsWith("[") ? new JSONArray(body) :
                    body.trim().startsWith("{") ? new JSONObject(body) : new JSONObject();
            if (status >= 400) {
                String detail = json instanceof JSONObject ?
                        ((JSONObject) json).optString("detail", "HTTP " + status) : "HTTP " + status;
                throw new Exception(detail);
            }
            return json;
        } finally {
            connection.disconnect();
        }
    }

    private JSONObject body(Object... pairs) throws JSONException {
        JSONObject result = new JSONObject();
        for (int i = 0; i < pairs.length; i += 2) result.put((String) pairs[i], pairs[i + 1]);
        return result;
    }

    private int dp(int amount) {
        return (int) (amount * getResources().getDisplayMetrics().density + 0.5f);
    }

    private LinearLayout vertical() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(14), dp(12), dp(14), dp(12));
        return box;
    }

    private TextView text(String value, int size, int color) {
        TextView label = new TextView(this);
        label.setText(value);
        label.setTextSize(size);
        label.setTextColor(color);
        label.setPadding(dp(5), dp(8), dp(5), dp(8));
        return label;
    }

    private Button button(String value, View.OnClickListener click) {
        Button b = new Button(this);
        b.setAllCaps(false);
        b.setText(value);
        b.setOnClickListener(click);
        return b;
    }

    private EditText edit(String hint, boolean secret) {
        EditText field = new EditText(this);
        field.setSingleLine(true);
        field.setTextColor(TEXT);
        field.setHintTextColor(MUTED);
        field.setHint(hint);
        field.setInputType(secret ?
                InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD :
                InputType.TYPE_CLASS_TEXT);
        return field;
    }

    private void setRoot(LinearLayout layout) {
        root = layout;
        root.setBackgroundColor(BACKGROUND);
        setContentView(root);
    }

    private void alert(String message) {
        new AlertDialog.Builder(this).setTitle("Beacon").setMessage(message)
                .setPositiveButton("OK", null).show();
    }

    private void loginScreen(String message) {
        activeBuddy = null;
        LinearLayout layout = vertical();
        layout.addView(text("◉ Beacon", 30, TEXT));
        layout.addView(text("Your people. Your network.", 16, MUTED));
        EditText address = edit("Server URL — http://192.168.1.10:8765", false);
        address.setText(server.isEmpty() ? "http://" : server);
        EditText username = edit("Username", false);
        EditText password = edit("Password", true);
        EditText device = edit("Device name", false);
        device.setText("Android · " + Build.MODEL);
        layout.addView(address);
        layout.addView(username);
        layout.addView(password);
        layout.addView(device);
        errorLabel = text(message, 13, MUTED);
        layout.addView(errorLabel);
        Button signIn = button("Sign in", v -> {
            String url = address.getText().toString().trim();
            try {
                URI uri = new URI(url);
                if (!("http".equals(uri.getScheme()) || "https".equals(uri.getScheme())) ||
                        uri.getHost() == null || uri.getRawUserInfo() != null ||
                        uri.getRawQuery() != null || uri.getRawFragment() != null ||
                        (uri.getRawPath() != null && !uri.getRawPath().equals("/") && !uri.getRawPath().isEmpty()))
                    throw new Exception("Invalid URL");
            } catch (Exception exception) {
                errorLabel.setText("Enter a valid http:// or https:// server address.");
                return;
            }
            String account = username.getText().toString().trim();
            String pass = password.getText().toString();
            String name = device.getText().toString().trim();
            if (account.isEmpty() || pass.isEmpty() || name.isEmpty()) {
                errorLabel.setText("All fields are required.");
                return;
            }
            server = url.replaceAll("/+$", "");
            signIn.setEnabled(false);
            errorLabel.setText("Signing in…");
            async(() -> request("/login", "POST", body(
                    "username", account, "password", pass,
                    "device_name", name.substring(0, Math.min(80, name.length())))),
                    (response, error) -> {
                        signIn.setEnabled(true);
                        if (error != null) { errorLabel.setText(error.getMessage()); return; }
                        JSONObject data = (JSONObject) response;
                        token = data.optString("token");
                        myUserId = data.optJSONObject("user").optInt("id");
                        authenticated = true;
                        currentStatus = "available";
                        stopMonitor();
                        if (!session.save(server, token))
                            Toast.makeText(this, "Keystore unavailable; login is temporary", Toast.LENGTH_LONG).show();
                        password.setText("");
                        previousUnread.clear();
                        initializedUnread = false;
                        rosterScreen();
                        restartTicker();
                    });
        });
        layout.addView(signIn);
        setRoot(layout);
    }

    private void rosterScreen() {
        activeBuddy = null;
        lastRosterFingerprint = "";
        LinearLayout layout = vertical();
        layout.addView(text("◉ Beacon · Buddy List", 24, TEXT));
        LinearLayout controls = new LinearLayout(this);
        controls.setOrientation(LinearLayout.HORIZONTAL);
        controls.addView(button("+ Buddy", v -> addBuddyDialog()));
        controls.addView(button("+ Group", v -> newGroupDialog()));
        controls.addView(button("Account", v -> accountMenu()));
        layout.addView(controls);
        LinearLayout statusBar = new LinearLayout(this);
        statusBar.setOrientation(LinearLayout.HORIZONTAL);
        for (String status : new String[]{"available", "away", "busy"}) {
            statusBar.addView(button(status, v -> {
                currentStatus = status;
                getSharedPreferences(BeaconMonitorService.PREFS, MODE_PRIVATE)
                    .edit().putString("status", status).apply();
                async(() ->
                    request("/presence", "POST", makeBody("status", status)),
                    (value, error) -> { if (error != null) alert(error.getMessage()); }); }));
        }
        layout.addView(statusBar);
        ScrollView scroller = new ScrollView(this);
        rosterList = vertical();
        scroller.addView(rosterList);
        layout.addView(scroller, new LinearLayout.LayoutParams(-1, 0, 1));
        setRoot(layout);
    }

    private JSONObject makeBody(Object... pairs) {
        try { return body(pairs); }
        catch (JSONException error) { throw new IllegalArgumentException(error); }
    }

    private void poll() {
        final Integer peer = activeBuddy;
        async(() -> {
            request("/presence", "POST", makeBody("status", currentStatus));
            JSONArray buddies = (JSONArray) request("/buddies", "GET", null);
            JSONArray groups = (JSONArray) request("/groups", "GET", null);
            JSONArray messages = peer == null ? null :
                    (JSONArray) request("/messages/" + peer, "GET", null);
            JSONObject typing = peer == null ? null :
                    (JSONObject) request("/typing/" + peer, "GET", null);
            if (messages != null) {
                int lastIncoming = 0;
                for (int i = 0; i < messages.length(); i++) {
                    JSONObject m = messages.getJSONObject(i);
                    if (m.optInt("sender_id") == peer)
                        lastIncoming = Math.max(lastIncoming, m.optInt("id"));
                }
                if (lastIncoming > 0)
                    request("/conversations/" + peer + "/read", "POST",
                            makeBody("through_id", lastIncoming));
            }
            return new Snapshot(buddies, groups, messages, typing, peer);
        }, (result, error) -> {
            if (error != null) return;
            Snapshot snap = result;
            knownBuddies.clear();
            knownGroups.clear();
            for (int i = 0; i < snap.buddies.length(); i++)
                knownBuddies.add(snap.buddies.optJSONObject(i));
            for (int i = 0; i < snap.groups.length(); i++)
                knownGroups.add(snap.groups.optJSONObject(i));
            for (JSONObject buddy : knownBuddies) {
                int id = buddy.optInt("id");
                int unread = buddy.optInt("unread_count");
                if (initializedUnread && unread > previousUnread.getOrDefault(id, unread) &&
                        buddy.optInt("muted") == 0 && (activeBuddy == null || id != activeBuddy))
                    notifyMessage(buddy);
                previousUnread.put(id, unread);
            }
            initializedUnread = true;
            if (activeBuddy == null) renderRoster(snap);
            else if (snap.peer != null && snap.peer.equals(activeBuddy)) renderChat(snap);
        });
    }

    private static final class Snapshot {
        final JSONArray buddies, groups, messages;
        final JSONObject typing;
        final Integer peer;
        Snapshot(JSONArray b, JSONArray g, JSONArray m, JSONObject t, Integer p) {
            buddies = b; groups = g; messages = m; typing = t; peer = p;
        }
    }

    private String buddyName(JSONObject buddy) {
        String alias = buddy.optString("nickname", "").trim();
        return alias.isEmpty() ? buddy.optString("display_name", "Unknown") : alias;
    }

    private ImageView photo(JSONObject user) {
        ImageView image = new ImageView(this);
        image.setLayoutParams(new LinearLayout.LayoutParams(dp(44), dp(44)));
        String value = user.optString("avatar", "");
        if (value.startsWith("data:image/") && value.contains(",")) {
            try {
                byte[] bytes = Base64.decode(value.substring(value.indexOf(',') + 1), Base64.DEFAULT);
                Bitmap bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
                if (bitmap != null) image.setImageBitmap(bitmap);
            } catch (IllegalArgumentException ignored) {}
        }
        if (image.getDrawable() == null) image.setImageResource(R.drawable.ic_beacon);
        return image;
    }

    private void renderRoster(Snapshot snap) {
        if (rosterList == null) return;
        String fingerprint = snap.buddies.toString() + snap.groups.toString();
        if (fingerprint.equals(lastRosterFingerprint)) return;
        lastRosterFingerprint = fingerprint;
        rosterList.removeAllViews();
        ArrayList<JSONObject> sections = new ArrayList<>();
        sections.add(makeBody("id", JSONObject.NULL, "name", "Buddies"));
        sections.addAll(knownGroups);
        for (JSONObject group : sections) {
            String name = group.optString("name");
            int groupId = group.isNull("id") ? -1 : group.optInt("id", -1);
            rosterList.addView(text(name, 19, Color.rgb(143, 200, 255)));
            int matched = 0;
            for (JSONObject buddy : knownBuddies) {
                int assigned = buddy.isNull("group_id") ? -1 : buddy.optInt("group_id", -1);
                if (assigned != groupId) continue;
                matched++;
                LinearLayout line = new LinearLayout(this);
                line.setBackgroundColor(SURFACE);
                line.setGravity(Gravity.CENTER_VERTICAL);
                line.setPadding(dp(8), dp(8), dp(8), dp(8));
                line.addView(photo(buddy));
                String state = buddy.optString("presence", "offline");
                String indicator = state.equals("available") ? "● " : state.equals("offline") ? "○ " : "◐ ";
                String title = indicator + buddyName(buddy);
                int unread = buddy.optInt("unread_count");
                if (unread > 0) title += " (" + unread + ")";
                if (buddy.optInt("muted") == 1) title += " 🔕";
                TextView label = text(title + "\n" + buddy.optString("status_text", state), 15, TEXT);
                line.addView(label, new LinearLayout.LayoutParams(0, -2, 1));
                int buddyId = buddy.optInt("id");
                line.setOnClickListener(v -> openChat(buddyId, buddyName(buddy)));
                line.setOnLongClickListener(v -> { buddyOptions(buddy); return true; });
                rosterList.addView(line);
            }
            if (matched == 0) rosterList.addView(text("No buddies in this group", 13, MUTED));
        }
    }

    private void openChat(int id, String name) {
        activeBuddy = id;
        activeName = name;
        rendered.clear();
        LinearLayout layout = vertical();
        LinearLayout title = new LinearLayout(this);
        title.setOrientation(LinearLayout.HORIZONTAL);
        title.addView(button("‹ Back", v -> { rosterScreen(); restartTicker(); }));
        title.addView(text(name, 21, TEXT));
        layout.addView(title);
        ScrollView scroll = new ScrollView(this);
        messageScroll = scroll;
        messagesList = vertical();
        scroll.addView(messagesList);
        layout.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        typingLabel = text("", 13, MUTED);
        layout.addView(typingLabel);
        LinearLayout composer = new LinearLayout(this);
        composer.setOrientation(LinearLayout.HORIZONTAL);
        inputMessage = edit("Message…", false);
        composer.addView(inputMessage, new LinearLayout.LayoutParams(0, -2, 1));
        composer.addView(button("Send", v -> sendMessage(id)), new LinearLayout.LayoutParams(dp(90), -2));
        layout.addView(composer);
        inputMessage.addTextChangedListener(new android.text.TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) {
                long now = System.currentTimeMillis();
                if (s.length() > 0 && now - lastTyping > 1600) {
                    lastTyping = now;
                    async(() -> request("/typing/" + id, "POST", makeBody("active", true)),
                            (value, error) -> {});
                }
            }
            @Override public void afterTextChanged(android.text.Editable value) {}
        });
        setRoot(layout);
        poll();
    }

    private void renderChat(Snapshot snap) {
        if (messagesList == null || snap.messages == null) return;
        for (int i = 0; i < snap.messages.length(); i++) {
            JSONObject message = snap.messages.optJSONObject(i);
            if (message == null) continue;
            int id = message.optInt("id");
            if (rendered.contains(id)) continue;
            rendered.add(id);
            boolean mine = message.optInt("sender_id") == myUserId;
            TextView bubble = text((mine ? "You" : activeName) + "\n" +
                    message.optString("body"), 16, TEXT);
            bubble.setBackgroundColor(mine ? Color.rgb(32, 91, 153) : SURFACE);
            LinearLayout.LayoutParams margins = new LinearLayout.LayoutParams(-1, -2);
            margins.setMargins(dp(8), dp(5), dp(8), dp(5));
            messagesList.addView(bubble, margins);
        }
        if (snap.typing != null && typingLabel != null)
            typingLabel.setText(snap.typing.optBoolean("active") ? activeName + " is typing…" : "");
        if (messageScroll != null) messageScroll.post(() -> messageScroll.fullScroll(View.FOCUS_DOWN));
    }

    private void sendMessage(int peer) {
        String text = inputMessage.getText().toString().trim();
        if (text.isEmpty()) return;
        inputMessage.setText("");
        async(() -> {
            Object value = request("/messages", "POST", makeBody("recipient_id", peer, "body", text));
            request("/typing/" + peer, "POST", makeBody("active", false));
            return value;
        }, (result, error) -> {
            if (error != null) {
                if (activeBuddy != null && activeBuddy == peer)
                    inputMessage.setText(text);
                alert(error.getMessage());
            } else poll();
        });
    }

    private void addBuddyDialog() {
        EditText name = edit("Buddy username", false);
        new AlertDialog.Builder(this).setTitle("Add a buddy").setView(name)
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Add", (dialog, which) -> {
                    String requested = name.getText().toString().trim();
                    async(() -> {
                        JSONArray users = (JSONArray) request("/directory", "GET", null);
                        for (int i = 0; i < users.length(); i++) {
                            JSONObject user = users.getJSONObject(i);
                            if (requested.equalsIgnoreCase(user.optString("username"))) {
                                return request("/buddies/" + user.getInt("id"), "POST", null);
                            }
                        }
                        throw new Exception("No user with that username");
                    }, (value, error) -> {
                        if (error != null) alert(error.getMessage());
                        else poll();
                    });
                }).show();
    }

    private void newGroupDialog() {
        EditText name = edit("Group name", false);
        new AlertDialog.Builder(this).setTitle("Create a buddy group").setView(name)
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Create", (d, which) ->
                        update("/groups", "POST", makeBody("name", name.getText().toString()))).show();
    }

    private void buddyOptions(JSONObject buddy) {
        int id = buddy.optInt("id");
        String[] options = {"Open IM", "Set nickname", "Move to group",
                buddy.optInt("muted") == 1 ? "Unmute alerts" : "Mute alerts", "Remove buddy"};
        new AlertDialog.Builder(this).setTitle(buddyName(buddy))
                .setItems(options, (d, choice) -> {
                    if (choice == 0) openChat(id, buddyName(buddy));
                    if (choice == 1) {
                        EditText name = edit("Nickname", false);
                        name.setText(buddy.optString("nickname"));
                        new AlertDialog.Builder(this).setTitle("Buddy nickname").setView(name)
                                .setNegativeButton("Cancel", null)
                                .setPositiveButton("Save", (dialog, which) ->
                                    update("/buddies/" + id + "/edit", "POST",
                                            makeBody("nickname", name.getText().toString()))).show();
                    }
                    if (choice == 2) {
                        String[] names = new String[knownGroups.size() + 1];
                        names[0] = "Buddies";
                        for (int i = 0; i < knownGroups.size(); i++)
                            names[i+1] = knownGroups.get(i).optString("name");
                        new AlertDialog.Builder(this).setTitle("Move buddy to group")
                                .setItems(names, (dialog, chosen) -> {
                                    Object groupId = chosen == 0 ? JSONObject.NULL :
                                            knownGroups.get(chosen - 1).optInt("id");
                                    update("/buddies/" + id + "/edit", "POST", makeBody("group_id", groupId));
                                }).show();
                    }
                    if (choice == 3)
                        update("/buddies/" + id + "/edit", "POST",
                                makeBody("muted", buddy.optInt("muted") != 1));
                    if (choice == 4)
                        new AlertDialog.Builder(this).setTitle("Remove buddy?")
                            .setMessage(buddyName(buddy))
                            .setNegativeButton("Cancel", null)
                            .setPositiveButton("Remove", (dialog, which) ->
                                update("/buddies/" + id, "DELETE", null)).show();
                }).show();
    }

    private void accountMenu() {
        String[] options = {"Rename a group", "Delete a group", "Change password",
                "Sign out other devices", monitorEnabled()
                    ? "Turn off background notifications" : "Turn on background notifications",
                "Sign out"};
        new AlertDialog.Builder(this).setTitle("Account and groups")
                .setItems(options, (dialog, which) -> {
                    if (which == 0 || which == 1) chooseGroup(which == 0);
                    if (which == 2) changePassword();
                    if (which == 3) new AlertDialog.Builder(this)
                            .setTitle("Revoke other devices?")
                            .setMessage("Keep this device signed in and revoke every other session?")
                            .setNegativeButton("Cancel", null)
                            .setPositiveButton("Revoke", (d, w) ->
                                    update("/sessions/revoke-others", "POST", makeBody()))
                            .show();
                    if (which == 4) {
                        if (monitorEnabled()) {
                            stopMonitor();
                            Toast.makeText(this, "Background monitoring stopped", Toast.LENGTH_SHORT).show();
                        } else {
                            new AlertDialog.Builder(this)
                                .setTitle("Keep Beacon listening?")
                                .setMessage("Beacon will show an ongoing Android notification and check your LAN server while the app is in the background. This uses battery and can stop if Android restricts the service. No cloud push provider is used.")
                                .setNegativeButton("Cancel", null)
                                .setPositiveButton("Enable", (d,w) -> startMonitor())
                                .show();
                        }
                    }
                    if (which == 5) logout();
                }).show();
    }

    private void chooseGroup(boolean rename) {
        if (knownGroups.isEmpty()) { alert("No custom groups yet."); return; }
        String[] names = new String[knownGroups.size()];
        for (int i = 0; i < knownGroups.size(); i++) names[i] = knownGroups.get(i).optString("name");
        new AlertDialog.Builder(this).setTitle(rename ? "Rename group" : "Delete group")
                .setItems(names, (dialog, index) -> {
                    int id = knownGroups.get(index).optInt("id");
                    if (rename) {
                        EditText name = edit("New name", false);
                        name.setText(names[index]);
                        new AlertDialog.Builder(this).setView(name)
                                .setNegativeButton("Cancel", null)
                                .setPositiveButton("Save", (d, w) ->
                                        update("/groups/" + id + "/rename", "POST",
                                                makeBody("name", name.getText().toString()))).show();
                    } else new AlertDialog.Builder(this).setTitle("Delete " + names[index] + "?")
                            .setMessage("Buddies will move to the default group.")
                            .setNegativeButton("Cancel", null)
                            .setPositiveButton("Delete", (d, w) ->
                                    update("/groups/" + id, "DELETE", null)).show();
                }).show();
    }

    private void changePassword() {
        LinearLayout form = vertical();
        EditText oldPassword = edit("Current password", true);
        EditText newPassword = edit("New password (12+ characters)", true);
        form.addView(oldPassword);
        form.addView(newPassword);
        new AlertDialog.Builder(this).setTitle("Change password").setView(form)
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Save", (d, w) ->
                    update("/me/password", "POST", makeBody(
                            "current_password", oldPassword.getText().toString(),
                            "new_password", newPassword.getText().toString()))).show();
    }

    private void update(String path, String method, JSONObject data) {
        async(() -> request(path, method, data), (value, error) -> {
            if (error != null) alert(error.getMessage());
            else poll();
        });
    }

    private boolean monitorEnabled() {
        return getSharedPreferences(BeaconMonitorService.PREFS, MODE_PRIVATE)
                .getBoolean("enabled", false);
    }

    private void startMonitor() {
        if (!authenticated || session.load() == null) {
            alert("Sign in and allow Beacon to remember your device before enabling background notifications.");
            return;
        }
        getSharedPreferences(BeaconMonitorService.PREFS, MODE_PRIVATE)
                .edit().putBoolean("enabled", true).putString("status", currentStatus).apply();
        Intent intent = new Intent(this, BeaconMonitorService.class)
                .setAction(BeaconMonitorService.ACTION_START);
        try {
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(intent);
            else startService(intent);
        } catch (RuntimeException failure) {
            stopMonitor();
            alert("Android prevented background monitoring: " + failure.getMessage());
        }
    }

    private void ensureMonitorIfEnabled() {
        if (monitorEnabled()) startMonitor();
    }

    private void stopMonitor() {
        getSharedPreferences(BeaconMonitorService.PREFS, MODE_PRIVATE)
                .edit().putBoolean("enabled", false).apply();
        stopService(new Intent(this, BeaconMonitorService.class));
    }

    private void logout() {
        stopMonitor();
        String currentToken = token;
        if (currentToken == null) { session.clear(); loginScreen(""); return; }
        final String logoutServer = server;
        worker.submit(() -> {
            HttpURLConnection connection = null;
            try {
                connection = (HttpURLConnection) new URL(logoutServer + "/api/logout").openConnection();
                connection.setRequestMethod("POST");
                connection.setRequestProperty("Authorization", "Bearer " + currentToken);
                connection.setConnectTimeout(5000);
                connection.setReadTimeout(5000);
                connection.getResponseCode();
            } catch (Exception ignored) {
                // Local token is always cleared, even if the server cannot be reached.
            } finally {
                if (connection != null) connection.disconnect();
            }
        });
        token = null;
        authenticated = false;
        session.clear();
        previousUnread.clear();
        initializedUnread = false;
        handler.removeCallbacks(ticker);
        loginScreen("");
    }

    @Override public void onBackPressed() {
        if (activeBuddy != null) {
            rosterScreen();
            restartTicker();
        } else super.onBackPressed();
    }

    private void notifyMessage(JSONObject buddy) {
        if (Build.VERSION.SDK_INT >= 33 &&
                checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
            return;
        NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        String name = buddyName(buddy);
        android.app.Notification notification = new android.app.Notification.Builder(this, "beacon_messages")
                .setSmallIcon(R.drawable.ic_beacon)
                .setContentTitle("New Beacon message")
                .setContentText(name + " sent you an IM")
                .setAutoCancel(true)
                .build();
        manager.notify(1000 + buddy.optInt("id"), notification);
    }
}
