package main

import (
	"bytes"
	"encoding/base64"
	"image"
	_ "image/jpeg"
	_ "image/png"
	"strings"
)

// Avatar payloads are provided by Beacon's authenticated API. Decode with
// strict size/pixel limits and no filesystem access or external fetches.
func paintAvatar(canvas *image.RGBA, value string, cx, cy, r int) bool {
	if !strings.HasPrefix(value, "data:image/") {
		return false
	}
	split := strings.SplitN(value, ",", 2)
	if len(split) != 2 || len(split[1]) > 700000 {
		return false
	}
	binary, e := base64.StdEncoding.DecodeString(split[1])
	if e != nil || len(binary) > 500000 {
		return false
	}
	boundsFormat, _, e := image.DecodeConfig(bytes.NewReader(binary))
	if e != nil || boundsFormat.Width < 1 || boundsFormat.Height < 1 || int64(boundsFormat.Width)*int64(boundsFormat.Height) > 8000000 {
		return false
	}
	bitmap, _, e := image.Decode(bytes.NewReader(binary))
	if e != nil {
		return false
	}
	bounds := bitmap.Bounds()
	for dy := -r; dy <= r; dy++ {
		for dx := -r; dx <= r; dx++ {
			if dx*dx+dy*dy > r*r {
				continue
			}
			xx := cx + dx
			yy := cy + dy
			if !image.Pt(xx, yy).In(canvas.Bounds()) {
				continue
			}
			// Square-crop centered within the source and resample into the circle.
			shortest := bounds.Dx()
			if bounds.Dy() < shortest {
				shortest = bounds.Dy()
			}
			srcX := bounds.Min.X + (bounds.Dx()-shortest)/2 + (dx+r)*shortest/(2*r+1)
			srcY := bounds.Min.Y + (bounds.Dy()-shortest)/2 + (dy+r)*shortest/(2*r+1)
			cr, cg, cb, _ := bitmap.At(srcX, srcY).RGBA()
			canvas.SetRGBA(xx, yy, colors.white)
			canvas.Set(xx, yy, colorFromRGBA(cr, cg, cb))
		}
	}
	return true
}
func colorFromRGBA(r, g, b uint32) imageColor {
	return imageColor{uint8(r >> 8), uint8(g >> 8), uint8(b >> 8), 255}
}

type imageColor struct{ r, g, b, a uint8 }

func (c imageColor) RGBA() (uint32, uint32, uint32, uint32) {
	return uint32(c.r) * 257, uint32(c.g) * 257, uint32(c.b) * 257, uint32(c.a) * 257
}
