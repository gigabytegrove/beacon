package main

import (
 "image/color"
 "errors"
 "strings"

 "github.com/gigabytegrove/beacon/clients/desktop-go/internal/beacon"

 "fyne.io/fyne/v2"
 "fyne.io/fyne/v2/canvas"
 "fyne.io/fyne/v2/container"
 "fyne.io/fyne/v2/theme"
 "fyne.io/fyne/v2/widget"
)

// Beacon design tokens are shared conceptually with Android's beacon_ values.
// These are flat, accessible foreground/background colors: no gradients, 3D or
// screen-sized background bitmaps.
var brand = struct{
 navy, blue, pale, white, ink, subtle, border, green, amber, red color.NRGBA
}{
 navy: color.NRGBA{R:9,G:23,B:45,A:255},
 blue: color.NRGBA{R:20,G:121,B:247,A:255},
 pale: color.NRGBA{R:243,G:246,B:252,A:255},
 white: color.NRGBA{R:255,G:255,B:255,A:255},
 ink: color.NRGBA{R:18,G:34,B:61,A:255},
 subtle: color.NRGBA{R:108,G:129,B:150,A:255},
 border: color.NRGBA{R:221,G:231,B:244,A:255},
 green: color.NRGBA{R:21,G:185,B:133,A:255},
 amber: color.NRGBA{R:245,G:168,B:62,A:255},
 red: color.NRGBA{R:220,G:83,B:98,A:255},
}

type beaconTheme struct{ fyne.Theme }
func(t beaconTheme) Color(name fyne.ThemeColorName, variant fyne.ThemeVariant) color.Color{
 switch name{
 case theme.ColorNameBackground: return brand.pale
 case theme.ColorNameForeground: return brand.ink
 case theme.ColorNamePrimary: return brand.blue
 case theme.ColorNameButton: return brand.white
 case theme.ColorNameInputBackground: return brand.white
 case theme.ColorNamePlaceHolder: return brand.subtle
 case theme.ColorNameSeparator: return brand.border
 case theme.ColorNameHover: return color.NRGBA{R:229,G:241,B:255,A:255}
 case theme.ColorNameFocus: return brand.blue
 case theme.ColorNameSelection: return color.NRGBA{R:217,G:236,B:255,A:255}
 case theme.ColorNameMenuBackground: return brand.white
 }
 return t.Theme.Color(name,fyne.ThemeVariantLight)
}
func(t beaconTheme) Size(name fyne.ThemeSizeName)float32{
 switch name {
 case theme.SizeNamePadding: return 9
 case theme.SizeNameText: return 14
 }
 return t.Theme.Size(name)
}

func beaconHeader(tagline string)fyne.CanvasObject{
 logo:=canvas.NewImageFromResource(&fyne.StaticResource{StaticName:"beacon.svg",StaticContent:iconBytes})
 logo.FillMode=canvas.ImageFillContain
 logo.SetMinSize(fyne.NewSize(54,54))
 brandTitle:=canvas.NewText("Beacon",brand.navy)
 brandTitle.TextStyle=fyne.TextStyle{Bold:true}
 brandTitle.TextSize=27
 subtitle:=widget.NewLabel(tagline)
 subtitle.Wrapping=fyne.TextWrapWord
 return container.NewBorder(nil,nil,logo,nil,container.NewVBox(brandTitle,subtitle))
}

func sectionHeading(title,subtitle string)fyne.CanvasObject{
 heading:=widget.NewLabelWithStyle(title,fyne.TextAlignLeading,fyne.TextStyle{Bold:true})
 if subtitle==""{return heading}
 hint:=widget.NewLabel(subtitle)
 hint.Wrapping=fyne.TextWrapWord
 return container.NewVBox(heading,hint)
}

func presenceDot(state string)fyne.CanvasObject{
 col:=brand.subtle
 switch state {
 case "available":col=brand.green
 case "away":col=brand.amber
 case "busy":col=brand.red
 }
 dot:=canvas.NewCircle(col)
 return container.NewGridWrap(fyne.NewSize(13,13),dot)
}

func noticeText(err error)string{
 if err==nil{return ""}
 message:=err.Error()
 lower:=strings.ToLower(message)
 switch{
 case errors.Is(err,beacon.ErrUnauthorized):
  return "Your session has expired. Please sign in again."
 case strings.Contains(lower,"connection refused"):
  return "The Beacon server refused the connection. Check the server address and Dokploy deployment."
 case strings.Contains(lower,"no such host"):
  return "That server name couldn't be resolved. Check the address or your network."
 case strings.Contains(lower,"deadline exceeded"),strings.Contains(lower,"timeout"):
  return "The server didn't respond in time. Check your network connection."
 case strings.Contains(lower,"certificate"):
  return "The server's HTTPS certificate couldn't be verified."
 }
 return message
}
