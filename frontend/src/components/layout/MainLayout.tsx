// frontend/src/components/layout/MainLayout.tsx
import React, {useEffect, useState} from 'react';
import {Outlet, useLocation, useNavigate} from 'react-router-dom';
import {
    AppBar,
    Avatar,
    Box,
    Button,
    CssBaseline,
    Divider,
    Drawer,
    IconButton,
    List,
    ListItem,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    Menu,
    MenuItem,
    Toolbar,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    AccountTree as AccountTreeIcon,
    Assignment as AssignmentIcon,
    ChevronLeft as ChevronLeftIcon,
    Factory as FactoryIcon,
    Inventory as InventoryIcon,
    Logout as LogoutIcon,
    Menu as MenuIcon,
    MenuOpen as MenuOpenIcon,
    Person as PersonIcon,
    QrCodeScanner as QrCodeScannerIcon,
    Schedule as ScheduleIcon,
    Science as ScienceIcon,
    Settings as SettingsIcon,
    ShoppingCart as ShoppingCartIcon,
    Timeline as TimelineIcon,
} from '@mui/icons-material';
import {useAuth} from '../../context/AuthContext';

const DRAWER_WIDTH_EXPANDED = 240;
const DRAWER_WIDTH_COLLAPSED = 56;
const STORAGE_KEY = 'aps_sidebar_collapsed';

const MENU_ITEMS = [
    { path: '/equipment', label: 'Оборудование', icon: <SettingsIcon /> },
    { path: '/products', label: 'Продукты', icon: <InventoryIcon /> },
    { path: '/materials', label: 'Материалы', icon: <InventoryIcon /> },
    { path: '/recipes', label: 'Рецептуры', icon: <ScienceIcon /> },
    { path: '/operations', label: 'Тех. карты', icon: <AccountTreeIcon /> },
    { path: '/orders', label: 'Заказы', icon: <ShoppingCartIcon /> },
    { path: '/schedule', label: 'Планирование', icon: <ScheduleIcon /> },
    { path: '/gantt', label: 'Диаграмма Ганта', icon: <TimelineIcon /> },
    { path: '/shift', label: 'Мастер смены', icon: <AssignmentIcon /> },
    { path: '/personnel', label: 'Персонал', icon: <PersonIcon /> },
    { path: '/cz', label: 'Честный Знак', icon: <QrCodeScannerIcon /> },   // Итерация 8
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

    const [collapsed, setCollapsed] = useState<boolean>(() => {
        return localStorage.getItem(STORAGE_KEY) === 'true';
    });

    useEffect(() => {
        localStorage.setItem(STORAGE_KEY, String(collapsed));
    }, [collapsed]);

    const handleToggleCollapse = () => setCollapsed((prev) => !prev);
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

    const currentDrawerWidth = collapsed ? DRAWER_WIDTH_COLLAPSED : DRAWER_WIDTH_EXPANDED;

    const drawerContent = (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <Toolbar
                sx={{
                    bgcolor: '#2c3e50',
                    color: 'white',
                    minHeight: '64px !important',
                    justifyContent: collapsed ? 'center' : 'flex-start',
                    px: collapsed ? 0 : 2,
                }}
            >
                <FactoryIcon sx={{ mr: collapsed ? 0 : 1, fontSize: 24 }} />
                {!collapsed && (
                    <Typography variant="h6" noWrap sx={{ fontWeight: 700, fontSize: '1.1rem' }}>
                        APS Scheduler
                    </Typography>
                )}
            </Toolbar>
            <Divider />

            <List sx={{ flexGrow: 1, pt: 1, px: collapsed ? 0.5 : 1 }}>
                {MENU_ITEMS.map((item) => {
                    const isActive = location.pathname === item.path;
                    const button = (
                        <ListItemButton
                            selected={isActive}
                            onClick={() => {
                                navigate(item.path);
                                setMobileOpen(false);
                            }}
                            sx={{
                                minHeight: 44,
                                justifyContent: collapsed ? 'center' : 'flex-start',
                                px: collapsed ? 1 : 2,
                                borderRadius: 1,
                                mb: 0.5,
                                '&.Mui-selected': {
                                    backgroundColor: '#3498db',
                                    color: 'white',
                                    '& .MuiListItemIcon-root': { color: 'white' },
                                    '&:hover': { backgroundColor: '#2980b9' },
                                },
                            }}
                        >
                            <ListItemIcon
                                sx={{
                                    minWidth: collapsed ? 0 : 40,
                                    justifyContent: 'center',
                                    color: isActive ? 'inherit' : '#2c3e50',
                                }}
                            >
                                {item.icon}
                            </ListItemIcon>
                            {!collapsed && (
                                <ListItemText
                                    primary={item.label}
                                    slotProps={{
                                        primary: { sx: { fontSize: '0.9rem' } },
                                    }}
                                />
                            )}
                        </ListItemButton>
                    );

                    return (
                        <ListItem key={item.path} disablePadding sx={{ display: 'block' }}>
                            {collapsed ? (
                                <Tooltip title={item.label} placement="right" arrow>
                                    {button}
                                </Tooltip>
                            ) : (
                                button
                            )}
                        </ListItem>
                    );
                })}
            </List>

            <Divider />
            <Box sx={{ p: collapsed ? 0.5 : 1 }}>
                <Tooltip title={collapsed ? 'Развернуть меню' : 'Свернуть меню'} placement="right" arrow>
                    <IconButton
                        onClick={handleToggleCollapse}
                        sx={{
                            width: '100%',
                            borderRadius: 1,
                            justifyContent: collapsed ? 'center' : 'flex-start',
                            px: collapsed ? 1 : 2,
                            py: 1,
                            color: '#2c3e50',
                            '&:hover': { backgroundColor: '#ecf0f1' },
                        }}
                    >
                        {collapsed ? <MenuIcon /> : <ChevronLeftIcon />}
                        {!collapsed && (
                            <Typography variant="body2" sx={{ ml: 1, fontSize: '0.85rem' }}>
                                Свернуть
                            </Typography>
                        )}
                    </IconButton>
                </Tooltip>
            </Box>
        </Box>
    );

    return (
        <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
            <CssBaseline />

            <AppBar
                position="fixed"
                sx={{
                    width: { md: `calc(100% - ${currentDrawerWidth}px)` },
                    ml: { md: `${currentDrawerWidth}px` },
                    bgcolor: '#2c3e50',
                    transition: 'width 0.2s, margin-left 0.2s',
                    zIndex: (theme) => theme.zIndex.drawer + 1,
                }}
            >
                <Toolbar sx={{ minHeight: '64px !important' }}>
                    <IconButton
                        color="inherit"
                        edge="start"
                        onClick={handleDrawerToggle}
                        sx={{ mr: 2, display: { md: 'none' } }}
                    >
                        <MenuIcon />
                    </IconButton>

                    <Tooltip title={collapsed ? 'Развернуть меню' : 'Свернуть меню'}>
                        <IconButton
                            color="inherit"
                            edge="start"
                            onClick={handleToggleCollapse}
                            sx={{ mr: 2, display: { xs: 'none', md: 'inline-flex' } }}
                        >
                            {collapsed ? <MenuOpenIcon /> : <MenuIcon />}
                        </IconButton>
                    </Tooltip>

                    <Typography variant="h6" noWrap sx={{ flexGrow: 1 }}>
                        {MENU_ITEMS.find((item) => item.path === location.pathname)?.label || 'APS Scheduler'}
                    </Typography>

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

            <Box component="nav" sx={{ width: { md: currentDrawerWidth }, flexShrink: { md: 0 } }}>
                <Drawer
                    variant="temporary"
                    open={mobileOpen}
                    onClose={handleDrawerToggle}
                    ModalProps={{ keepMounted: true }}
                    sx={{
                        display: { xs: 'block', md: 'none' },
                        '& .MuiDrawer-paper': {
                            boxSizing: 'border-box',
                            width: DRAWER_WIDTH_EXPANDED,
                        },
                    }}
                >
                    {drawerContent}
                </Drawer>

                <Drawer
                    variant="permanent"
                    sx={{
                        display: { xs: 'none', md: 'block' },
                        '& .MuiDrawer-paper': {
                            boxSizing: 'border-box',
                            width: currentDrawerWidth,
                            overflowX: 'hidden',
                            transition: 'width 0.2s',
                            borderRight: '1px solid #e0e0e0',
                        },
                    }}
                    open
                >
                    {drawerContent}
                </Drawer>
            </Box>

            <Box
                component="main"
                sx={{
                    flexGrow: 1,
                    width: { md: `calc(100% - ${currentDrawerWidth}px)` },
                    height: '100vh',
                    display: 'flex',
                    flexDirection: 'column',
                    overflow: 'hidden',
                    bgcolor: '#f5f6fa',
                    transition: 'width 0.2s',
                }}
            >
                <Toolbar sx={{ minHeight: '64px !important', flexShrink: 0 }} />
                <Box
                    sx={{
                        flexGrow: 1,
                        minHeight: 0,
                        overflow: 'hidden',
                        p: 3,
                        display: 'flex',
                        flexDirection: 'column',
                    }}
                >
                    <Outlet />
                </Box>
            </Box>
        </Box>
    );
};

export default MainLayout;