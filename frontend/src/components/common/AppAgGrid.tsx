// frontend/src/components/common/AppAgGrid.tsx
import React from 'react';
import {AgGridReact, type AgGridReactProps} from 'ag-grid-react';
import {agGridTheme} from '../../theme/agGridTheme';
import {AG_GRID_LOCALE_RU} from '../../theme/agGridLocale';

export interface AppAgGridProps extends AgGridReactProps {
    theme?: AgGridReactProps['theme'];
    localeText?: AgGridReactProps['localeText'];
}

export const AppAgGrid: React.FC<AppAgGridProps> = ({
                                                        theme,
                                                        localeText,
                                                        ...rest
                                                    }) => {
    return (
        <AgGridReact
            theme={theme ?? agGridTheme}
            localeText={localeText ?? AG_GRID_LOCALE_RU}
            {...rest}
        />
    );
};

export default AppAgGrid;