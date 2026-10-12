//go:build !windows

package main

import "fmt"

func dockBuddyList() error { return fmt.Errorf("right-edge docking is currently available on Windows") }
func undockBuddyList() error { return nil }
