package net.gigabytegrove.beacon;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * Explicitly opted-in, notification-visible LAN message monitor.
 * No Google push dependency; background delivery is best-effort and depends on
 * Android's foreground-service policy and the device remaining on the LAN.
 */
public final class BeaconMonitorService extends Service {
    public static final String ACTION_START = "net.gigabytegrove.beacon.START_MONITOR";
    public static final String ACTION_STOP = "net.gigabytegrove.beacon.STOP_MONITOR";
    public static final String PREFS = "beacon_monitor";
    private static final String CHANNEL_STATUS = "beacon_connection";
    private static final String CHANNEL_MESSAGES = "beacon_messages";
    private static final int STATUS_ID = 101;
    private ScheduledExecutorService executor;
    private SharedPreferences prefs;
    private String server;
    private String token;
    private String cursorKey;

    @Override public void onCreate() {
        super.onCreate();
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        manager.createNotificationChannel(new NotificationChannel(
                CHANNEL_STATUS, "Beacon background connection", NotificationManager.IMPORTANCE_LOW));
        manager.createNotificationChannel(new NotificationChannel(
                CHANNEL_MESSAGES, "Beacon messages", NotificationManager.IMPORTANCE_DEFAULT));
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            prefs.edit().putBoolean("enabled", false).apply();
            stopSelf();
            return START_NOT_STICKY;
        }
        if (intent == null || !ACTION_START.equals(intent.getAction()) ||
                !prefs.getBoolean("enabled", false)) {
            stopSelf();
            return START_NOT_STICKY;
        }
        String[] auth = new SecureSession(this).load();
        if (auth == null) {
            prefs.edit().putBoolean("enabled", false).apply();
            stopSelf();
            return START_NOT_STICKY;
        }
        server = auth[0];
        token = auth[1];
        try {
            byte[] hash = MessageDigest.getInstance("SHA-256")
                    .digest(token.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder();
            for (int i = 0; i < 12; i++) hex.append(String.format("%02x", hash[i] & 0xff));
            cursorKey = "cursor_" + hex;
            Notification notice = foregroundNotification();
            if (Build.VERSION.SDK_INT >= 34) {
                startForeground(STATUS_ID, notice, ServiceInfo.FOREGROUND_SERVICE_TYPE_REMOTE_MESSAGING);
            } else {
                startForeground(STATUS_ID, notice);
            }
        } catch (Exception failure) {
            prefs.edit().putBoolean("enabled", false).apply();
            stopSelf();
            return START_NOT_STICKY;
        }
        if (executor == null || executor.isShutdown()) {
            executor = Executors.newSingleThreadScheduledExecutor();
            executor.scheduleWithFixedDelay(this::pollSafely, 0, 7, TimeUnit.SECONDS);
        }
        return START_NOT_STICKY;
    }

    private Notification foregroundNotification() {
        Intent open = new Intent(this, MainActivity.class);
        PendingIntent openIntent = PendingIntent.getActivity(this, 0, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Intent stop = new Intent(this, BeaconMonitorService.class).setAction(ACTION_STOP);
        PendingIntent stopIntent = PendingIntent.getService(this, 2, stop,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        return new Notification.Builder(this, CHANNEL_STATUS)
                .setSmallIcon(R.drawable.ic_beacon)
                .setContentTitle("Beacon is listening on your LAN")
                .setContentText("Background message notifications enabled")
                .setContentIntent(openIntent)
                .setOngoing(true)
                .addAction(new Notification.Action.Builder(null, "Stop", stopIntent).build())
                .build();
    }

    private JSONObject request(String path) throws Exception {
        HttpURLConnection connection = (HttpURLConnection)
                new URL(server + "/api" + path).openConnection();
        try {
            connection.setRequestProperty("Authorization", "Bearer " + token);
            connection.setRequestProperty("Accept", "application/json");
            connection.setConnectTimeout(5000);
            connection.setReadTimeout(5000);
            int code = connection.getResponseCode();
            if (code == 401) throw new SecurityException("Session was revoked");
            if (code != 200) throw new java.io.IOException("HTTP " + code);
            try (InputStream input = connection.getInputStream();
                 ByteArrayOutputStream buffer = new ByteArrayOutputStream()) {
                byte[] chunk = new byte[4096];
                int count;
                while ((count = input.read(chunk)) != -1) buffer.write(chunk, 0, count);
                return new JSONObject(buffer.toString("UTF-8"));
            }
        } finally {
            connection.disconnect();
        }
    }

    private JSONArray buddies() throws Exception {
        HttpURLConnection connection = (HttpURLConnection)
                new URL(server + "/api/buddies").openConnection();
        try {
            connection.setRequestProperty("Authorization", "Bearer " + token);
            connection.setConnectTimeout(5000);
            connection.setReadTimeout(5000);
            int code = connection.getResponseCode();
            if (code == 401) throw new SecurityException("Session was revoked");
            if (code != 200) throw new java.io.IOException("HTTP " + code);
            try (InputStream input = connection.getInputStream();
                 ByteArrayOutputStream output = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[4096];
                int count;
                while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
                return new JSONArray(output.toString("UTF-8"));
            }
        } finally {
            connection.disconnect();
        }
    }

    private void updatePresence() throws Exception {
        String status = prefs.getString("status", "available");
        if (!("available".equals(status) || "away".equals(status) || "busy".equals(status))) {
            status = "available";
        }
        HttpURLConnection connection = (HttpURLConnection)
                new URL(server + "/api/presence").openConnection();
        try {
            connection.setConnectTimeout(5000);
            connection.setReadTimeout(5000);
            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setRequestProperty("Authorization", "Bearer " + token);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            byte[] payload = ("{\"status\":\"" + status + "\"}").getBytes(StandardCharsets.UTF_8);
            try (java.io.OutputStream stream = connection.getOutputStream()) {
                stream.write(payload);
            }
            int code = connection.getResponseCode();
            if (code == 401) throw new SecurityException("Session was revoked");
            if (code != 200) throw new java.io.IOException("Presence HTTP " + code);
        } finally {
            connection.disconnect();
        }
    }

    private void pollSafely() {
        if (Thread.currentThread().isInterrupted()) return;
        try {
            updatePresence();
            // Server persists messages before notifying clients.
            // This cursor survives network failures, app restarts, and Doze delays.
            if (!prefs.contains(cursorKey)) {
                JSONObject baseline = request("/events/latest");
                long latest = baseline.getLong("last_message_id");
                prefs.edit().putLong(cursorKey, latest).commit();
                // Do not replay existing history as new notifications when the
                // user first enables monitoring; future messages use this cursor.
                return;
            }
            boolean hadCursor = true;
            long cursor = prefs.getLong(cursorKey, 0);
            Map<Integer, JSONObject> contacts = new HashMap<>();
            JSONArray buddies = buddies();
            for (int i = 0; i < buddies.length(); i++) {
                JSONObject buddy = buddies.optJSONObject(i);
                if (buddy != null) contacts.put(buddy.optInt("id"), buddy);
            }
            int pages = 0;
            while (pages++ < 10 && !Thread.currentThread().isInterrupted()) {
                JSONObject result = request("/events?after=" + cursor + "&limit=200");
                JSONArray events = result.getJSONArray("events");
                for (int i = 0; i < events.length(); i++) {
                    JSONObject event = events.getJSONObject(i);
                    long id = event.getLong("id");
                    if (id <= cursor) continue;
                    cursor = id;
                    int sender = event.optInt("sender_id");
                    JSONObject buddy = contacts.get(sender);
                    if (hadCursor && !prefs.getBoolean("activity_visible", false) &&
                            buddy != null && buddy.optInt("muted", 0) == 0 &&
                            buddy.optInt("unread_count", 0) > 0) {
                        showMessage(buddy, event);
                    }
                    prefs.edit().putLong(cursorKey, cursor).apply();
                }
                if (events.length() < 200) break;
            }
            if (!hadCursor) prefs.edit().putLong(cursorKey, cursor).apply();
        } catch (SecurityException invalid) {
            // Revoked tokens are never used again.
            prefs.edit().putBoolean("enabled", false).apply();
            stopSelf();
        } catch (Exception unavailable) {
            // Keep the cursor unchanged and retry on the next LAN check.
        }
    }

    private void showMessage(JSONObject buddy, JSONObject message) {
        if (Build.VERSION.SDK_INT >= 33 &&
                checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            return;
        }
        PendingIntent open = PendingIntent.getActivity(this, 0,
                new Intent(this, MainActivity.class)
                        .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        String nickname = buddy.optString("nickname", "");
        String person = nickname.isEmpty() ? buddy.optString("display_name", "Buddy") : nickname;
        String body = message.optString("body", "");
        Notification notice = new Notification.Builder(this, CHANNEL_MESSAGES)
                .setSmallIcon(R.drawable.ic_beacon)
                .setContentTitle(person + " sent you a Beacon IM")
                .setContentText(body.length() > 180 ? body.substring(0, 180) : body)
                .setContentIntent(open)
                .setAutoCancel(true)
                .build();
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        manager.notify((int) (message.optLong("id") % 1_000_000) + 2000, notice);
    }

    @Override public void onDestroy() {
        if (executor != null) {
            executor.shutdownNow();
            executor = null;
        }
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) {
        return null;
    }
}
