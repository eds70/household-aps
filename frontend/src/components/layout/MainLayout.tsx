// frontend/src/components/layout/MainLayout.tsx
import React, { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
    AppBar,
    Box,
    CssBaseline,
    Divider,
    Drawer,
    IconButton,
    List,
    ListItem,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    Toolbar,
    Typography,
    Tooltip,
    Avatar,
    Menu,
    MenuItem,
    Button,
} from '@mui/material';
import {
    Menu as MenuIcon,
    Factory as FactoryIcon,
    Inventory as InventoryIcon,
    Settings as SettingsIcon,
    Timeline as TimelineIcon,
    Schedule as ScheduleIcon,
    AccountTree as AccountTreeIcon,
    ShoppingCart as ShoppingCartIcon,
    Science as ScienceIcon,
    Logout as LogoutIcon,
    Person as PersonIcon,
} from '@mui/icons-material';
import { useAuth } from '../../context/AuthContext';

const DRAWER_WIDTH = 260;

const MENU_ITEMS = [
    { path: '/equipment', label: 'Оборудование', icon: <SettingsIcon /> },
    { path: '/products', label: 'Продукты', icon: <InventoryIcon /> },
    { path: '/materials', label: 'Материалы', icon: <InventoryIcon /> },
    { path: '/recipes', label: 'Рецептуры', icon: <ScienceIcon /> },
    { path: '/operations', label: 'Тех. карты', icon: <AccountTreeIcon /> },
    { path: '/orders', label: 'Заказы', icon: <ShoppingCartIcon /> },
    { path: '/schedule', label: 'Планирование', icon: <ScheduleIcon /> },
    { path: '/gantt', label: 'Диаграмма Ганта', icon: <TimelineIcon /> },
];

const ROLE_LABELS: Record<string, string> = {
    ADMIN: 'Администратор',
    PLANNER: 'Планировщик',
    MASTER: 'Мастер',
    LAB: 'Лаборант',
    VIEWER: 'Наблюдатель',
};

const MainLayout: React.FC = () => {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();
    const [mobileOpen, setMobileOpen] = useState(false);
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

    const handleDrawerToggle = () => setMobileOpen(!mobileOpen);

    const handleProfileClick = (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
    };

    const handleProfileClose = () => {
        setAnchorEl(null);
    };

    const handleLogout = () => {
        handleProfileClose();
        logout();
        navigate('/login');
    };

    const drawer = (
        <Box>
            <Toolbar sx={{ bgcolor: '#2c3e50', color: 'white' }}>
                <FactoryIcon sx={{ mr: 1 }} />
                <Typography variant="h6" noWrap sx={{ fontWeight: 700 }}>
                    APS Scheduler
                </Typography>
            </Toolbar>
            <Divider />
            <List>
                {MENU_ITEMS.map((item) => {
                    const isActive = location.pathname === item.path;
                    return (
                        <ListItem key={item.path} disablePadding>
                            <ListItemButton
                                selected={isActive}
                                onClick={() => {
                                    navigate(item.path);
                                    setMobileOpen(false);
                                }}
                                sx={{
                                    '&.Mui-selected': {
                                        backgroundColor: '#3498db',
                                        color: 'white',
                                        '& .MuiListItemIcon-root': { color: 'white' },
                                        '&:hover': { backgroundColor: '#2980b9' },
                                    },
                                }}
                            >
                                <ListItemIcon>{item.icon}</ListItemIcon>
                                <ListItemText primary={item.label} />
                            </ListItemButton>
                        </ListItem>
                    );
                })}
            </List>
        </Box>
    );

    return (
        <Box sx={{ display: 'flex', minHeight: '100vh' }}>
            <CssBaseline />

            {/* AppBar */}
            <AppBar
                position="fixed"
                sx={{
                    width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
                    ml: { md: `${DRAWER_WIDTH}px` },
                    bgcolor: '#2c3e50',
                }}
            >
                <Toolbar>
                    <IconButton
                        color="inherit"
                        edge="start"
                        onClick={handleDrawerToggle}
                        sx={{ mr: 2, display: { md: 'none' } }}
                    >
                        <MenuIcon />
                    </IconButton>

                    <Typography variant="h6" noWrap sx={{ flexGrow: 1 }}>
                        {MENU_ITEMS.find((item) => item.path === location.pathname)?.label || 'APS Scheduler'}
                    </Typography>

                    {/* Профиль пользователя */}
                    {user && (
                        <>
                            <Tooltip title="Профиль">
                                <Button
                                    color="inherit"
                                    onClick={handleProfileClick}
                                    startIcon={
                                        <Avatar sx={{ width: 32, height: 32, bgcolor: '#3498db', fontSize: '0.9rem' }}>
                                            {user.email.charAt(0).toUpperCase()}
                                        </Avatar>
                                    }
                                    sx={{ textTransform: 'none' }}
                                >
                                    <Box sx={{ textAlign: 'left', display: { xs: 'none', sm: 'block' } }}>
                                        <Typography variant="body2" sx={{ lineHeight: 1.2, fontWeight: 600 }}>
                                            {user.full_name || user.email}
                                        </Typography>
                                        <Typography variant="caption" sx={{ lineHeight: 1, opacity: 0.8 }}>
                                            {ROLE_LABELS[user.role] || user.role}
                                        </Typography>
                                    </Box>
                                </Button>
                            </Tooltip>

                            <Menu
                                anchorEl={anchorEl}
                                open={Boolean(anchorEl)}
                                onClose={handleProfileClose}
                                transformOrigin={{ horizontal: 'right', vertical: 'top' }}
                                anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
                            >
                                <MenuItem disabled>
                                    <PersonIcon sx={{ mr: 1 }} />
                                    {user.email}
                                </MenuItem>
                                <Divider />
                                <MenuItem onClick={handleLogout}>
                                    <LogoutIcon sx={{ mr: 1 }} />
                                    Выйти
                                </MenuItem>
                            </Menu>
                        </>
                    )}
                </Toolbar>
            </AppBar>

            {/* Drawer */}
            <Box component="nav" sx={{ width: { md: DRAWER_WIDTH }, flexShrink: { md: 0 } }}>
                <Drawer
                    variant="temporary"
                    open={mobileOpen}
                    onClose={handleDrawerToggle}
                    ModalProps={{ keepMounted: true }}
                    sx={{
                        display: { xs: 'block', md: 'none' },
                        '& .MuiDrawer-paper': { boxSizing: 'border-box', width: DRAWER_WIDTH },
                    }}
                >
                    {drawer}
                </Drawer>
                <Drawer
                    variant="permanent"
                    sx={{
                        display: { xs: 'none', md: 'block' },
                        '& .MuiDrawer-paper': { boxSizing: 'border-box', width: DRAWER_WIDTH },
                    }}
                    open
                >
                    {drawer}
                </Drawer>
            </Box>

            {/* Main content */}
            <Box
                component="main"
                sx={{
                    flexGrow: 1,
                    p: 3,
                    width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
                    minHeight: '100vh',
                    bgcolor: '#f5f6fa',
                }}
            >
                <Toolbar />
                <Outlet />
            </Box>
        </Box>
    );
};

export default MainLayout;