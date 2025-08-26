import React from "react";
import { Link, useLocation } from "react-router-dom";
import AppBar from "@mui/material/AppBar";
import Toolbar from "@mui/material/Toolbar";
import IconButton from "@mui/material/IconButton";
import Typography from "@mui/material/Typography";
import Button from "@mui/material/Button";
import Tooltip from "@mui/material/Tooltip";
import { useThemeMode } from "../theme/ThemeProvider.jsx";
import DarkModeOutlinedIcon from '@mui/icons-material/DarkModeOutlined';
import LightModeOutlinedIcon from '@mui/icons-material/LightModeOutlined';
import LiveTvOutlinedIcon from '@mui/icons-material/LiveTvOutlined';

export default function Navbar() {
  const location = useLocation();
  const isActive = (path) =>
    location.pathname === path ? "text-foreground" : "text-muted-foreground";

  const { mode, toggle } = useThemeMode();

  return (
    <AppBar position="sticky" color="transparent" elevation={0} sx={{ backdropFilter: 'blur(8px)', borderBottom: '1px solid', borderColor: 'divider' }}>
      <Toolbar sx={{ maxWidth: 1200, mx: 'auto', width: '100%' }}>
        <LiveTvOutlinedIcon sx={{ mr: 1 }} />
        <Typography variant="h6" component={Link} to="/users" sx={{ color: 'text.primary', textDecoration: 'none', flexGrow: 1 }}>
          StreamHub
        </Typography>
        <Button component={Link} to="/users" color="inherit" sx={{ mr: 1 }}>
          Users
        </Button>
        <Button component={Link} to="/streamers" color="inherit" sx={{ mr: 2 }}>
          Streamers
        </Button>
        <Tooltip title="Toggle theme">
          <IconButton onClick={toggle} color="inherit" sx={{ mr: 1 }}>
            {mode === 'dark' ? <LightModeOutlinedIcon /> : <DarkModeOutlinedIcon />}
          </IconButton>
        </Tooltip>
        <Button component={Link} to="/logout" variant="outlined" color="inherit" size="small">
          Logout
        </Button>
      </Toolbar>
    </AppBar>
  );
}


