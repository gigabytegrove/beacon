package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
)

// Save only non-secret preferences. Never persist bearer tokens or passwords.
type localPreferences struct {
	Server string `json:"server"`
}

func preferencePath() string {
	folder, e := os.UserConfigDir()
	if e != nil {
		return ""
	}
	return filepath.Join(folder, "BeaconMessenger", "preferences.json")
}
func previousServer() string {
	path := preferencePath()
	if path == "" {
		return ""
	}
	data, e := os.ReadFile(path)
	if e != nil || len(data) > 4096 {
		return ""
	}
	var pref localPreferences
	if json.Unmarshal(data, &pref) != nil {
		return ""
	}
	// An invalid local configuration should not put arbitrary network addresses into the UI.
	if strings.HasPrefix(pref.Server, "http://") || strings.HasPrefix(pref.Server, "https://") {
		return pref.Server
	}
	return ""
}
func rememberServer(addr string) {
	path := preferencePath()
	if path == "" {
		return
	}
	if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
		return
	}
	data, _ := json.Marshal(localPreferences{Server: addr})
	tmp := path + ".tmp"
	if e := os.WriteFile(tmp, data, 0600); e != nil {
		return
	}
	_ = os.Rename(tmp, path)
}
