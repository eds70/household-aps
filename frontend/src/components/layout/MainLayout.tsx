// frontend/src/components/layout/MainLayout.tsx
import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
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
    Chip,
} from '@mui/material';
import {
    Menu as MenuIcon,
    Factory as FactoryIcon,
    Inventory as InventoryIcon,
    Settings as SettingsIcon,
    Timeline as TimelineIcon,
    Build as BuildIcon,
    ChevronLeft as ChevronLeftIcon,
    ChevronRight as ChevronRightIcon,
    EventNote as EventNoteIcon,
    Edit as EditIcon,
    Science as ScienceIcon,
    ShoppingCart as CartIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { usePlan } from '../../context/PlainContext';

const drawerWidth = 240;
const drawerCollapsedWidth = 64;

const menuItems = [
    { text: 'Оборудование', icon: <BuildIcon />, path: '/equipment' },
    { text: 'Продукты', icon: <InventoryIcon />, path: '/products' },
    { text: 'Материалы', icon: <ScienceIcon />, path: '/materials' },
    { text: 'Рецептуры', icon: <ScienceIcon />, path: '/recipes' },
    { text: 'Тех. карты', icon: <SettingsIcon />, path: '/operations' },
    { text: 'Заказы', icon: <CartIcon />, path: '/orders' },
    { text: 'Планирование', icon: <FactoryIcon />, path: '/schedule' },
    { text: 'Диаграмма Ганта', icon: <TimelineIcon />, path: '/gantt' },
];

const MainLayout: React.FC = () => {
    const [mobileOpen, setMobileOpen] = useState(false);
    const [collapsed, setCollapsed] = useState(false);
    const navigate = useNavigate();
    const location = useLocation();

    const { currentVersionId, currentPlanName } = usePlan();

    const handleDrawerToggle = () => setMobileOpen(!mobileOpen);
    const handleCollapseToggle = () => setCollapsed(!collapsed);

    const currentDrawerWidth = collapsed ? drawerCollapsedWidth : drawerWidth;

    const drawer = (
        <div>
            <Toolbar sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                {!collapsed && (
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <FactoryIcon sx={{ mr: 1 }} />
                        <Typography variant="h6" noWrap component="div">APS Scheduler</Typography>
                    </Box>
                )}
                <IconButton onClick={handleCollapseToggle} sx={{ display: { xs: 'none', sm: 'flex' } }}>
                    {collapsed ? <ChevronRightIcon /> : <ChevronLeftIcon />}
                </IconButton>
            </Toolbar>
            <Divider />
            <List>
                {menuItems.map((item) => (
                    <ListItem key={item.text} disablePadding>
                        <Tooltip title={collapsed ? item.text : ''} placement="right">
                            <ListItemButton
                                selected={location.pathname === item.path}
                                onClick={() => navigate(item.path)}
                                sx={{ minHeight: 48, justifyContent: collapsed ? 'center' : 'initial', px: 2.5 }}
                            >
                                <ListItemIcon sx={{ minWidth: 0, mr: collapsed ? 'auto' : 3, justifyContent: 'center' }}>
                                    {item.icon}
                                </ListItemIcon>
                                {!collapsed && <ListItemText primary={item.text} />}
                            </ListItemButton>
                        </Tooltip>
                    </ListItem>
                ))}
            </List>
        </div>
    );

    return (
        <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
            <CssBaseline />
            <AppBar
                position="fixed"
                sx={{
                    width: { sm: `calc(100% - ${currentDrawerWidth}px)` },
                    ml: { sm: `${currentDrawerWidth}px` },
                    transition: 'width 0.3s, margin-left 0.3s',
                }}
            >
                <Toolbar>
                    <IconButton
                        color="inherit"
                        aria-label="open drawer"
                        edge="start"
                        onClick={handleDrawerToggle}
                        sx={{ mr: 2, display: { sm: 'none' } }}
                    >
                        <MenuIcon />
                    </IconButton>

                    <Box sx={{ display: 'flex', flexDirection: 'column', lineHeight: 1.2 }}>
                        <Typography variant="h6" component="div" sx={{ fontWeight: 600 }}>
                            Система планирования производства
                        </Typography>
                        {currentVersionId ? (
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.25 }}>
                                <EventNoteIcon sx={{ fontSize: 14, opacity: 0.9 }} />
                                <Typography variant="caption" sx={{ color: '#90caf9', fontWeight: 500, fontSize: '0.75rem' }}>
                                    {currentPlanName}
                                </Typography>
                            </Box>
                        ) : (
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.25 }}>
                                <EditIcon sx={{ fontSize: 14, opacity: 0.7 }} />
                                <Typography variant="caption" sx={{ color: '#ffcc80', fontWeight: 500, fontSize: '0.75rem' }}>
                                    {currentPlanName}
                                </Typography>
                            </Box>
                        )}
                    </Box>

                    <Box sx={{ ml: 'auto', display: 'flex', alignItems: 'center' }}>
                        <Chip
                            label={currentVersionId ? 'ПРОСМОТР' : 'РЕДАКТИРОВАНИЕ'}
                            size="small"
                            sx={{
                                bgcolor: currentVersionId ? 'rgba(33, 150, 243, 0.2)' : 'rgba(255, 152, 0, 0.2)',
                                color: 'white',
                                fontWeight: 600,
                            }}
                        />
                    </Box>
                </Toolbar>
            </AppBar>

            <Box component="nav" sx={{ width: { sm: currentDrawerWidth }, flexShrink: { sm: 0 }, transition: 'width 0.3s' }}>
                <Drawer
                    variant="temporary"
                    open={mobileOpen}
                    onClose={handleDrawerToggle}
                    ModalProps={{ keepMounted: true }}
                    sx={{ display: { xs: 'block', sm: 'none' }, '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth } }}
                >
                    {drawer}
                </Drawer>
                <Drawer
                    variant="permanent"
                    sx={{
                        display: { xs: 'none', sm: 'block' },
                        '& .MuiDrawer-paper': { boxSizing: 'border-box', width: currentDrawerWidth, transition: 'width 0.3s', overflowX: 'hidden' },
                    }}
                    open
                >
                    {drawer}
                </Drawer>
            </Box>

            <Box
                component="main"
                sx={{
                    flexGrow: 1,
                    p: 3,
                    width: { sm: `calc(100% - ${currentDrawerWidth}px)` },
                    transition: 'width 0.3s',
                    overflow: 'auto',
                    height: '100vh',
                    display: 'flex',
                    flexDirection: 'column',
                }}
            >
                <Toolbar />
                <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                    <Outlet />
                </Box>
            </Box>
        </Box>
    );
};

export default MainLayout;